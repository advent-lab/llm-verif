"""CovAgent v2 multi-agent parent graph.

Implements the Orchestrator-Expert-Generator architecture using LangGraph.
Structurally mirrors react.py (v1) but the agent is the Orchestrator, and
the tools layer invokes specialist subagents (Design Expert, Test Generators)
instead of simulation tools directly.

Graph topology:
    initialize → agent → (route) → tools → update_state → prune_context
                                                                ↓
                              ← ← ← ← ← ← ← ← ← ← (route: continue/finalize/END)

    finalize → agent → (write_file?) → tools → END
"""

from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage, RemoveMessage
import json as _json
import logging
from pathlib import Path

from ..state.schemas import MultiAgentState
from ..config import Config, load_config
from ..utils.design_loader import extract_all_module_headers
from ..utils.tokens import count_message_tokens, format_token_count
from ..utils.token_tracking import extract_usage_from_response, build_token_record, classify_pending_records
from ..utils.agent_logging import log_agent_request, log_agent_response, Colors
from ..utils.event_log import (
    init_event_log, emit, serialize_message, serialize_config, get_git_info,
)
from ..prompts.loader import load_orchestrator_prompt
from ..tools.coverage import update_coverage_cache, get_coverage_status
from ..tools.analysis import _create_annotated_source
from ..tools import set_tool_config

from .agents.design_expert import create_design_expert
from .agents.orchestrator import make_orchestrator_tools

# ── Module-level state (non-serializable, set during graph creation) ──────
_config: Config = None
_expert_graph = None
_expert_thread_id: str = None
_orchestrator_tools: list = None
_gen_context: dict = None  # {"iteration": int, "next_gen_id": int}
_adapter = None  # Simulator adapter for coverage merging

# Cumulative token counters for token_count events
_cumulative_tokens = {
    "input_tokens": 0,
    "output_tokens": 0,
    "reasoning_tokens": 0,
    "cached_input_tokens": 0,
    "total_tokens": 0,
}


# ── Graph Nodes ───────────────────────────────────────────────────────────

def initialize_node(state: MultiAgentState) -> MultiAgentState:
    """Initialize node: one-time setup of the multi-agent environment.

    Steps:
    1. Create work directory structure
    2. Extract module headers (top-level + all submodules for registry)
    3. Construct orchestrator system prompt
    4. Initialize event log
    """
    config = _config
    logging.info("Initializing multi-agent workflow (v2)")

    # Create work directory structure
    (config.work_dir / "testbenches").mkdir(parents=True, exist_ok=True)
    (config.work_dir / "logs").mkdir(parents=True, exist_ok=True)
    (config.work_dir / "coverage").mkdir(parents=True, exist_ok=True)
    (config.work_dir / "sim_work").mkdir(parents=True, exist_ok=True)

    logging.info(f"Work directory: {config.work_dir}")
    logging.info(f"Design: {config.design_name}")
    logging.info(f"Architecture: v2 (Orchestrator-Expert-Generator)")

    # Extract module headers
    module_header = extract_all_module_headers(config.design_files)

    # Build module registry (all modules across all files)
    module_registry = _build_module_registry(config)

    # Build module registry summary for the orchestrator prompt
    registry_summary = _format_module_registry(module_registry)

    # Construct orchestrator system prompt
    orchestrator_prompt = load_orchestrator_prompt(
        design_name=config.design_name,
        module_header=module_header,
        module_registry_summary=registry_summary,
        max_iterations=config.max_iterations,
        sim_runs=config.sim_runs,
        sim_timeout=config.sim_timeout,
        design_dir=str(config.design_dir),
        spec_path=str(config.spec_path),
        design_files=config.design_files,
        design_context_files=config.design_context_files,
    )

    # Set config for filesystem tools (used by orchestrator directly)
    set_tool_config(config)

    # Initialize structured event log
    init_event_log(config.work_dir / "events.jsonl")

    emit("session_start", {
        "config": serialize_config(config),
        "git": get_git_info(),
        "architecture": "v2",
        "agents": {
            "orchestrator_model": config.orchestrator_model,
            "design_expert_model": config.design_expert_model,
            "test_generator_model": config.test_generator_model,
        },
    })

    emit("system_prompt", {
        "content": orchestrator_prompt,
        "content_length": len(orchestrator_prompt),
        "agent": "orchestrator",
    })

    init_human_msg = (
        f"Begin verification for {config.design_name}. "
        f"Start by querying the Design Expert to understand the design "
        f"and create a verification plan."
    )

    emit("human_message", {"source": "init", "content": init_human_msg})

    return {
        "messages": [
            SystemMessage(content=orchestrator_prompt),
            HumanMessage(content=init_human_msg),
        ],
        "config": config,
        "design_name": config.design_name,
        "design_dir": str(config.design_dir),
        "spec_path": str(config.spec_path),
        "design_files": [str(f) for f in config.design_files],
        "design_context_files": [str(f) for f in config.design_context_files],
        "module_header": module_header,
        "module_registry": module_registry,
        "work_dir": str(config.work_dir),
        "testplan_path": None,
        "coverage_tracking_path": None,
        "iteration": 1,
        "cumulative_coverage": 0.0,
        "cumulative_coverage_db": None,
        "coverage_history": [],
        "no_progress_count": 0,
        "api_calls": 0,
        "orchestrator_calls": 0,
        "design_expert_calls": 0,
        "test_generator_dispatches": 0,
        "consecutive_gen_failures": 0,
        "functional_coverage_enabled": config.functional_coverage_enabled,
        "current_functional_coverage": 0.0,
        "max_functional_coverage": 0.0,
        "uncovered_bins": [],
        "is_done": False,
        "done_reason": None,
        "is_finalizing": False,
        "token_usage": [],
    }


def agent_node(state: MultiAgentState) -> MultiAgentState:
    """Orchestrator agent node: LLM reasoning and tool selection."""
    global _cumulative_tokens

    config = state["config"]

    # Create LLM
    llm_kwargs = dict(
        model=config.orchestrator_model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        api_key=config.openai_api_key,
    )
    if config.reasoning_effort != "disabled":
        llm_kwargs["reasoning_effort"] = config.reasoning_effort
    llm = ChatOpenAI(**llm_kwargs)

    # Bind orchestrator tools
    llm_with_tools = llm.bind_tools(_orchestrator_tools)

    # Increment API call counter
    new_api_calls = state.get("api_calls", 0) + 1
    request_state = dict(state)
    request_state["api_calls"] = new_api_calls

    log_agent_request(request_state)

    # Emit api_request event
    messages = state.get("messages", [])
    latest_serialized = [serialize_message(msg) for msg in messages[-10:]]
    emit("api_request", {
        "api_call": new_api_calls,
        "iteration": state.get("iteration", 1),
        "agent": "orchestrator",
        "message_count": len(messages),
        "estimated_input_tokens": count_message_tokens(messages, config.orchestrator_model),
        "latest_messages": latest_serialized,
    })

    # Invoke LLM
    from ..utils.conversation_logger import get_logger
    response = llm_with_tools.invoke(
        state["messages"],
        config={"callbacks": [get_logger("orchestrator")]},
    )

    # Extract token usage
    usage = extract_usage_from_response(response)

    emit("reasoning", {
        "api_call": new_api_calls,
        "agent": "orchestrator",
        "content": response.content if hasattr(response, "content") else None,
        "content_length": len(response.content) if hasattr(response, "content") and response.content else 0,
    })

    # Emit tool_call events
    tool_call_names = []
    tool_call_args = []
    if hasattr(response, 'tool_calls') and response.tool_calls:
        for i, tc in enumerate(response.tool_calls):
            tool_call_names.append(tc.get('name', 'unknown'))
            tool_call_args.append(tc.get('args', {}))
            emit("tool_call", {
                "api_call": new_api_calls,
                "call_index": i,
                "agent": "orchestrator",
                "tool_name": tc.get("name", "unknown"),
                "arguments": tc.get("args", {}),
                "call_id": tc.get("id", ""),
            })

    # Token tracking
    last_usage = {
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "reasoning_tokens": usage.get("reasoning_tokens", 0),
        "cached_input_tokens": usage.get("cached_input_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }
    for key in _cumulative_tokens:
        _cumulative_tokens[key] += last_usage.get(key, 0)

    emit("token_count", {
        "api_call": new_api_calls,
        "agent": "orchestrator",
        "last_usage": last_usage,
        "cumulative_usage": dict(_cumulative_tokens),
    })

    token_record = build_token_record(
        api_call_num=new_api_calls,
        iteration=state.get("iteration", 1),
        usage=usage,
        tool_calls=tool_call_names,
        tool_call_args=tool_call_args,
        failures=state.get("consecutive_gen_failures", 0),
        cumulative_coverage=state.get("cumulative_coverage", 0.0),
    )

    log_agent_response(response, request_state, usage)

    # Track no-tool-call count
    if hasattr(response, 'tool_calls') and response.tool_calls:
        no_tool_call_count = 0
    else:
        no_tool_call_count = state.get("_no_tool_call_count", 0) + 1

    return {
        "messages": [response],
        "api_calls": new_api_calls,
        "orchestrator_calls": state.get("orchestrator_calls", 0) + 1,
        "token_usage": [token_record],
        "_no_tool_call_count": no_tool_call_count,
    }


def update_state_node(state: MultiAgentState) -> MultiAgentState:
    """Process tool results: merge coverage, generate feedback, update state.

    Handles:
    - dispatch_test_generator results: merge coverage DBs, generate feedback
    - query_design_expert results: increment expert call counter
    - Other tools: no state changes needed
    """
    config = state["config"]
    messages = state.get("messages", [])

    # Classify pending token records
    classify_pending_records(state)

    # Scope scanning to ONLY ToolMessages from the current turn (after the
    # last AIMessage).  Without this, old dispatch_test_generator ToolMessages
    # from prior iterations stay in the [-20:] window and get re-processed,
    # creating phantom iterations and inflating the iteration counter.
    last_ai_idx = None
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], AIMessage):
            last_ai_idx = i
            break
    current_turn_msgs = messages[last_ai_idx + 1:] if last_ai_idx is not None else []

    gen_results = []
    expert_calls = 0

    for msg in current_turn_msgs:
        if not hasattr(msg, 'name'):
            continue
        if msg.name == 'dispatch_test_generator':
            try:
                content = msg.content if isinstance(msg.content, str) else _json.dumps(msg.content)
                parsed = _json.loads(content)
                if isinstance(parsed, dict):
                    gen_results.append(parsed)
            except (ValueError, TypeError):
                pass
        elif msg.name == 'query_design_expert':
            expert_calls += 1

    # If no generators completed, just track expert calls
    if not gen_results:
        delta = {}
        if expert_calls > 0:
            delta["design_expert_calls"] = state.get("design_expert_calls", 0) + expert_calls
        emit("state_update", {"trigger": "no_generators", "delta": delta})
        return delta

    # Process generator results
    successful_dbs = []
    for r in gen_results:
        if r.get("success") and r.get("coverage_db_path"):
            db_path = Path(r["coverage_db_path"])
            if db_path.exists():
                successful_dbs.append(db_path)

    total_dispatches = state.get("test_generator_dispatches", 0) + len(gen_results)
    failed_count = len(gen_results) - len(successful_dbs)

    if not successful_dbs:
        # All generators failed
        new_failures = state.get("consecutive_gen_failures", 0) + 1  # +1 per failed iteration, not per agent
        delta = {
            "test_generator_dispatches": total_dispatches,
            "consecutive_gen_failures": new_failures,
            "design_expert_calls": state.get("design_expert_calls", 0) + expert_calls,
        }
        emit("state_update", {"trigger": "all_generators_failed", "delta": delta})
        return delta

    # Merge all successful coverage DBs into cumulative
    func_cov_enabled = getattr(config, 'functional_coverage_enabled', False)
    cumulative_db_path = Path(config.work_dir) / "coverage" / "cumulative.ucdb"
    prev_coverage = state.get("cumulative_coverage", 0.0)
    delta_pct = 0.0  # defined here so it's always in scope after the if/else
    for db_path in successful_dbs:
        try:
            _adapter.merge_cumulative_coverage(db_path, cumulative_db_path)
        except Exception as e:
            logging.error(f"Coverage merge failed for {db_path}: {e}")

    if func_cov_enabled:
        # Functional coverage mode: parse funcov only
        new_coverage = prev_coverage
        new_func_coverage = state.get("current_functional_coverage", 0.0)
        new_uncovered_bins = state.get("uncovered_bins", [])
        try:
            func_result = _adapter.parse_functional_coverage(cumulative_db_path)
            new_func_coverage = func_result.get("total_coverage", 0.0)
            new_uncovered_bins = []
            for cg in func_result.get("covergroups", []):
                for bin_entry in cg.get("uncovered_bins", []):
                    if isinstance(bin_entry, dict):
                        new_uncovered_bins.append({
                            "covergroup": cg["name"],
                            "instance_path": cg.get("instance_path", ""),
                            "coverpoint": bin_entry.get("coverpoint", ""),
                            "coverpoint_kind": bin_entry.get("coverpoint_kind", "Coverpoint"),
                            "bin_name": bin_entry.get("bin_name", ""),
                            "covergroup_coverage": cg.get("coverage", 0.0),
                            "sample_event": cg.get("sample_event"),
                        })
            logging.info(f"Functional coverage: {new_func_coverage:.2f}% ({len(new_uncovered_bins)} bins uncovered)")
        except Exception as e:
            logging.error(f"Functional coverage parse failed: {e}")

        update_coverage_cache(
            cumulative_coverage=0.0,
            iteration=state.get("iteration", 1),
            breakdown={},
            uncovered_lines={},
            annotated_source="",
            gen_results=gen_results,
            prev_coverage=0.0,
            functional_coverage_enabled=True,
            functional_coverage=new_func_coverage,
            uncovered_bins=new_uncovered_bins,
        )
        tracking_content = _build_funcov_tracking(
            new_func_coverage, new_uncovered_bins,
            state.get("iteration", 1), config.functional_coverage_target,
        )
        tracking_path = Path(config.work_dir) / "coverage_tracking.md"
        tracking_path.write_text(tracking_content, encoding='utf-8')

        prev_func = state.get("current_functional_coverage", 0.0)
        func_delta = new_func_coverage - prev_func
        feedback_msg = HumanMessage(content=(
            f"[COVERAGE UPDATE] Iteration {state.get('iteration', 1)} complete.\n"
            f"Functional coverage: {new_func_coverage:.2f}% "
            f"(was {prev_func:.2f}%, {'+' if func_delta >= 0 else ''}{func_delta:.2f}%). "
            f"Uncovered bins: {len(new_uncovered_bins)}.\n"
            f"Generators: {len(gen_results)} ({len(successful_dbs)} succeeded, {failed_count} failed).\n"
            f"Use `get_coverage_status` for detailed bin breakdown."
        ))
    else:
        # Code coverage mode: parse code coverage only
        new_func_coverage = 0.0
        new_uncovered_bins = []
        cumulative_result = None
        try:
            cumulative_result = _adapter.parse_coverage(cumulative_db_path)
            new_coverage = cumulative_result.total_coverage
        except Exception as e:
            logging.error(f"Cumulative coverage parse failed: {e}")
            new_coverage = prev_coverage

        if cumulative_result:
            max_holes = getattr(config, 'num_feedback_holes', 0)
            annotated_source = _create_annotated_source(
                cumulative_result.uncovered_lines, max_holes
            )
            update_coverage_cache(
                cumulative_coverage=new_coverage,
                iteration=state.get("iteration", 1),
                breakdown=cumulative_result.breakdown,
                uncovered_lines=cumulative_result.uncovered_lines,
                annotated_source=annotated_source,
                gen_results=gen_results,
                prev_coverage=prev_coverage,
                functional_coverage_enabled=False,
                functional_coverage=0.0,
                uncovered_bins=[],
            )
            tracking_content = _build_coverage_tracking(
                new_coverage, cumulative_result.breakdown,
                cumulative_result.uncovered_lines, state.get("iteration", 1),
            )
            tracking_path = Path(config.work_dir) / "coverage_tracking.md"
            tracking_path.write_text(tracking_content, encoding='utf-8')
        else:
            tracking_path = state.get("coverage_tracking_path")

        delta_pct = new_coverage - prev_coverage
        feedback_msg = HumanMessage(content=(
            f"[COVERAGE UPDATE] Iteration {state.get('iteration', 1)} complete.\n"
            f"Cumulative coverage: {new_coverage:.2f}% "
            f"(was {prev_coverage:.2f}%, {'+' if delta_pct >= 0 else ''}{delta_pct:.2f}%).\n"
            f"Generators dispatched: {len(gen_results)} "
            f"({len(successful_dbs)} succeeded, {failed_count} failed).\n"
            f"Use `get_coverage_status` for detailed breakdown."
        ))

    emit("coverage_merge", {
        "iteration": state.get("iteration", 1),
        "dbs_merged": len(successful_dbs),
        "cumulative_coverage": new_coverage,
        "delta": delta_pct,
    })

    # Update iteration and progress tracking
    next_iteration = state.get("iteration", 1) + 1
    _gen_context["iteration"] = next_iteration
    _gen_context["next_gen_id"] = 0

    progress_cov = new_func_coverage if func_cov_enabled else new_coverage
    prev_progress = state.get("current_functional_coverage", 0.0) if func_cov_enabled else prev_coverage
    if progress_cov > prev_progress:
        no_progress = 0
        logging.info(f"{'Functional c' if func_cov_enabled else 'C'}overage improved: {prev_progress:.2f}% → {progress_cov:.2f}%")
    else:
        no_progress = state.get("no_progress_count", 0) + 1
        logging.warning(f"No {'functional ' if func_cov_enabled else ''}coverage improvement: {progress_cov:.2f}%")

    delta = {
        "messages": [feedback_msg],
        "iteration": next_iteration,
        "cumulative_coverage": new_coverage,
        "cumulative_coverage_db": str(cumulative_db_path),
        "current_functional_coverage": new_func_coverage,
        "max_functional_coverage": max(state.get("max_functional_coverage", 0.0), new_func_coverage),
        "uncovered_bins": new_uncovered_bins,
        "coverage_history": state.get("coverage_history", []) + [{
            "iteration": state.get("iteration", 1),
            "coverage": new_coverage,
            "functional_coverage": new_func_coverage,
            "delta": delta_pct,
            "generators": len(gen_results),
        }],
        "coverage_tracking_path": str(tracking_path) if tracking_path else None,
        "no_progress_count": no_progress,
        "consecutive_gen_failures": 0 if successful_dbs else state.get("consecutive_gen_failures", 0) + 1,
        "test_generator_dispatches": total_dispatches,
        "design_expert_calls": state.get("design_expert_calls", 0) + expert_calls,
    }

    emit("state_update", {
        "trigger": "generators_complete",
        "iteration": next_iteration,
        "cumulative_coverage": new_coverage,
        "delta": delta_pct,
        "no_progress_count": no_progress,
    })

    return delta


def finalize_node(state: MultiAgentState) -> MultiAgentState:
    """Inject message telling the orchestrator to write its final report."""
    config = state["config"]
    cumulative_coverage = state.get("cumulative_coverage", 0.0)
    no_progress = state.get("no_progress_count", 0)
    iteration = state.get("iteration", 0)
    api_calls = state.get("api_calls", 0)
    consecutive_failures = state.get("consecutive_gen_failures", 0)
    token_count = count_message_tokens(state["messages"], config.orchestrator_model)

    # Determine termination reason
    func_cov_enabled = getattr(config, 'functional_coverage_enabled', False)
    func_cov_target = getattr(config, 'functional_coverage_target', 100.0)
    if func_cov_enabled:
        effective_coverage = state.get("current_functional_coverage", 0.0)
        coverage_complete = effective_coverage >= func_cov_target
    else:
        effective_coverage = cumulative_coverage
        coverage_complete = effective_coverage >= 100.0
    if coverage_complete:
        reason = "coverage_complete"
    elif token_count >= config.context_window:
        reason = "context_window_limit"
    elif api_calls >= config.max_iterations:
        reason = "max_api_calls"
    elif consecutive_failures >= config.max_retries:
        reason = "max_retries"
    elif no_progress >= config.max_no_progress:
        reason = "no_progress"
    else:
        reason = "unknown"

    if func_cov_enabled:
        cov_line = f"Final functional coverage: {effective_coverage:.2f}%."
        report_coverage = (
            "- Final functional coverage and remaining uncovered bins\n"
            "- Which bins could not be covered and why\n"
        )
    else:
        cov_line = f"Final cumulative coverage: {cumulative_coverage:.2f}%."
        report_coverage = (
            "- Classification of ALL remaining uncovered lines "
            "(unreachable, excludable, potential bugs, needs more effort)\n"
        )

    finalize_message = (
        f"FRAMEWORK NOTICE: Verification terminated (reason: {reason}). "
        f"{cov_line} "
        f"Iterations completed: {iteration - 1}. "
        f"Expert queries: {state.get('design_expert_calls', 0)}. "
        f"Generator dispatches: {state.get('test_generator_dispatches', 0)}.\n\n"
        f"You MUST now write your final run report to `report.md` using `write_file`. "
        f"This is your LAST turn — only `write_file` tool calls will be executed.\n\n"
        f"The report MUST include:\n"
        f"- Final coverage and iteration count\n"
        f"{report_coverage}"
        f"- Summary of strategies used (top-level vs unit-level, what worked)\n"
        f"- Recommendations for future work"
    )

    logging.info(f"{Colors.MAGENTA}{Colors.BOLD}{'='*80}{Colors.RESET}")
    logging.info(f"{Colors.MAGENTA}{Colors.BOLD}FINALIZE ({reason}): "
                 f"Giving orchestrator one last turn to write report.md{Colors.RESET}")
    logging.info(f"{Colors.MAGENTA}Coverage: {effective_coverage:.2f}% | "
                 f"No-progress: {no_progress} | "
                 f"Expert calls: {state.get('design_expert_calls', 0)} | "
                 f"Gen dispatches: {state.get('test_generator_dispatches', 0)}"
                 f"{Colors.RESET}")
    logging.info(f"{Colors.MAGENTA}{'='*80}{Colors.RESET}\n")

    emit("finalize", {
        "reason": reason,
        "cumulative_coverage": effective_coverage,
        "iterations_completed": iteration - 1,
    })

    emit("human_message", {"source": "finalize", "content": finalize_message})

    return {
        "messages": [HumanMessage(content=finalize_message)],
        "is_finalizing": True,
        "done_reason": reason,
    }


def prune_context(state: MultiAgentState) -> dict:
    """Remove old coverage update messages and stale tool results.

    Keeps only the latest [COVERAGE UPDATE] HumanMessage and prunes
    old generator dispatch pairs to manage context growth.
    """
    messages = state.get("messages", [])

    # Find all coverage update messages
    coverage_msgs = []
    for msg in messages:
        if (isinstance(msg, HumanMessage) and
            hasattr(msg, 'content') and
            isinstance(msg.content, str) and
            msg.content.startswith("[COVERAGE UPDATE]")):
            coverage_msgs.append(msg)

    # Keep only the latest coverage update
    remove_msgs = []
    if len(coverage_msgs) > 1:
        for msg in coverage_msgs[:-1]:
            remove_msgs.append(RemoveMessage(id=msg.id))

    if remove_msgs:
        logging.info(f"Context pruning: removing {len(remove_msgs)} old coverage update(s)")
        emit("context_prune", {
            "messages_removed": len(remove_msgs),
            "policy": "keep_latest_coverage_update",
        })

    return {"messages": remove_msgs} if remove_msgs else {}


# ── Routing Functions ─────────────────────────────────────────────────────

def route_after_agent(state: MultiAgentState) -> Literal["tools", "agent", "finalize", "__end__"]:
    """Route after orchestrator decision."""
    config = state["config"]
    last_message = state["messages"][-1]

    def _route(decision, reason):
        emit("route_decision", {
            "source": "after_agent",
            "decision": decision,
            "reason": reason,
            "api_calls": state.get("api_calls", 0),
            "iteration": state.get("iteration", 1),
        })
        return decision

    # In finalize mode: only allow write_file tool calls
    if state.get("is_finalizing", False):
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            write_calls = [tc for tc in last_message.tool_calls if tc.get('name') == 'write_file']
            if write_calls:
                last_message.tool_calls = write_calls
                return _route("tools", "finalize: executing write_file")
        return _route(END, "finalize: no write_file call, ending")

    # Check termination conditions
    if state["api_calls"] >= config.max_iterations:
        return _route("finalize", f"max_api_calls ({state['api_calls']}/{config.max_iterations})")

    if state.get("consecutive_gen_failures", 0) >= config.max_retries:
        return _route("finalize", f"max_retries ({state['consecutive_gen_failures']}/{config.max_retries})")

    if state.get("no_progress_count", 0) >= config.max_no_progress:
        return _route("finalize", f"max_no_progress ({state['no_progress_count']}/{config.max_no_progress})")

    # Check context window
    token_count = count_message_tokens(state["messages"], config.orchestrator_model)
    if token_count >= config.context_window:
        return _route("finalize", f"context_window_limit ({token_count:,}/{config.context_window:,})")

    # Route to tools if tool calls present
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        tool_names = [tc.get('name', '?') for tc in last_message.tool_calls]
        return _route("tools", f"tool_calls: {tool_names}")

    # No tool calls — check if stuck
    no_tool_count = state.get("_no_tool_call_count", 0)
    if no_tool_count >= config.max_no_tool_calls:
        return _route("finalize", f"max_no_tool_calls ({no_tool_count}/{config.max_no_tool_calls})")

    return _route("agent", "no_tool_calls, retrying")


def route_after_update(state: MultiAgentState) -> Literal["agent", "finalize", "__end__"]:
    """Route after state update — check termination with updated state."""
    config = state["config"]

    def _route(decision, reason):
        emit("route_decision", {
            "source": "after_update",
            "decision": decision,
            "reason": reason,
            "api_calls": state.get("api_calls", 0),
            "iteration": state.get("iteration", 1),
            "cumulative_coverage": state.get("cumulative_coverage", 0.0),
        })
        return decision

    if state.get("is_finalizing", False):
        return _route(END, "finalize_turn_complete")

    func_cov_enabled = getattr(config, 'functional_coverage_enabled', False)
    func_cov_target = getattr(config, 'functional_coverage_target', 100.0)
    if func_cov_enabled:
        cumulative = state.get("current_functional_coverage", 0.0)
        target = func_cov_target
    else:
        cumulative = state.get("cumulative_coverage", 0.0)
        target = 100.0
    if cumulative >= target:
        return _route("finalize", f"coverage_complete ({cumulative:.2f}%)")

    if state["api_calls"] >= config.max_iterations:
        return _route("finalize", f"max_api_calls ({state['api_calls']}/{config.max_iterations})")

    if state.get("consecutive_gen_failures", 0) >= config.max_retries:
        return _route("finalize", f"max_retries ({state['consecutive_gen_failures']}/{config.max_retries})")

    if state.get("no_progress_count", 0) >= config.max_no_progress:
        return _route("finalize", f"max_no_progress ({state['no_progress_count']}/{config.max_no_progress})")

    token_count = count_message_tokens(state["messages"], config.orchestrator_model)
    if token_count >= config.context_window:
        return _route("finalize", f"context_window_limit ({token_count:,}/{config.context_window:,})")

    return _route("agent", "continue")


# ── Helper Functions ──────────────────────────────────────────────────────

def _build_module_registry(config: Config) -> dict:
    """Build a registry of all module headers across all design files.

    Returns:
        Dict mapping module_name -> header_string for every module
        found in design_files and design_context_files.
    """
    from ..utils.design_loader import extract_module_headers_per_module
    registry = {}
    all_files = list(config.design_files) + list(config.design_context_files)
    for f in all_files:
        try:
            headers = extract_module_headers_per_module(f)
            registry.update(headers)
        except Exception as e:
            logging.warning(f"Failed to extract headers from {f}: {e}")
    return registry


def _format_module_registry(registry: dict) -> str:
    """Format module registry as a summary string for the orchestrator prompt."""
    if not registry:
        return "(no modules extracted)"
    lines = []
    for name, header in sorted(registry.items()):
        # Truncate long headers
        short = header.split('\n')[0][:100]
        lines.append(f"  - {name}: {short}")
    return "\n".join(lines)


def _build_coverage_tracking(
    coverage: float,
    breakdown: dict,
    uncovered_lines: dict,
    iteration: int,
) -> str:
    """Build the coverage_tracking.md artifact content."""
    total_uncovered = sum(len(lines) for lines in uncovered_lines.values())

    parts = [
        f"# Remaining Coverage Holes — Iteration {iteration}",
        f"",
        f"## Code Coverage: {coverage:.2f}% (target: 100%)",
        f"",
        f"Total uncovered lines: {total_uncovered}",
        f"",
    ]

    for file_path, lines in sorted(uncovered_lines.items()):
        if not lines:
            continue
        filename = Path(file_path).name
        cov = breakdown.get(file_path, 0.0)
        parts.append(f"### {filename} ({len(lines)} uncovered, {cov:.1f}% covered)")

        # Group into ranges
        sorted_lines = sorted(set(lines))
        ranges = []
        start = sorted_lines[0]
        end = sorted_lines[0]
        for line in sorted_lines[1:]:
            if line == end + 1:
                end = line
            else:
                ranges.append(f"{start}-{end}" if start != end else str(start))
                start = end = line
        ranges.append(f"{start}-{end}" if start != end else str(start))

        for r in ranges:
            parts.append(f"- Lines {r}")
        parts.append("")

    return "\n".join(parts)


def _build_funcov_tracking(
    func_coverage: float,
    uncovered_bins: list,
    iteration: int,
    target: float,
) -> str:
    """Build the coverage_tracking.md artifact for functional coverage mode."""
    by_cg: dict = {}
    for b in uncovered_bins:
        cg = b.get("covergroup", "unknown")
        by_cg.setdefault(cg, []).append(b)

    parts = [
        f"# Remaining Coverage Bins — Iteration {iteration}",
        "",
        f"## Functional Coverage: {func_coverage:.2f}% (target: {target:.0f}%)",
        "",
        f"Total uncovered bins: {len(uncovered_bins)}",
        "",
    ]
    for cg_name, bins in sorted(by_cg.items()):
        parts.append(f"### {cg_name} ({len(bins)} uncovered bins)")
        for b in bins:
            cp = b.get("coverpoint", "?")
            bn = b.get("bin_name", "?")
            parts.append(f"- {cp}: `{bn}`")
        parts.append("")

    return "\n".join(parts)


# ── Graph Factory ─────────────────────────────────────────────────────────

def create_multi_agent_graph():
    """Create the v2 multi-agent parent graph.

    Pre-initializes all agents and tools before graph compilation.
    Returns a compiled StateGraph ready for invocation.
    """
    global _config, _expert_graph, _expert_thread_id, _orchestrator_tools
    global _gen_context, _adapter

    # Load config
    _config = load_config()

    # Create simulator adapter for coverage merging
    simulator_type = getattr(_config, 'simulator_type', 'questasim').lower()
    if simulator_type == 'questasim':
        from ..simulators.questasim_adapter import QuestasimAdapter
        _adapter = QuestasimAdapter(_config.simulator_path)
    elif simulator_type == 'verilator':
        from ..simulators.verilator_adapter import VerilatorAdapter
        _adapter = VerilatorAdapter(_config.simulator_path)

    # Create Design Expert
    _expert_graph, _expert_thread_id = create_design_expert(_config)

    # Create generator context (mutable, updated by update_state_node)
    _gen_context = {"iteration": 1, "next_gen_id": 0}

    # Create orchestrator tools
    _orchestrator_tools = make_orchestrator_tools(
        _config, _expert_graph, _expert_thread_id, _gen_context,
    )

    # Build graph
    graph = StateGraph(MultiAgentState)

    graph.add_node("initialize", initialize_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(_orchestrator_tools))
    graph.add_node("update_state", update_state_node)
    graph.add_node("prune_context", prune_context)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("initialize")
    graph.add_edge("initialize", "agent")

    graph.add_conditional_edges(
        "agent",
        route_after_agent,
        {
            "tools": "tools",
            "agent": "agent",
            "finalize": "finalize",
            END: END,
        }
    )

    graph.add_edge("tools", "update_state")
    graph.add_edge("update_state", "prune_context")

    graph.add_conditional_edges(
        "prune_context",
        route_after_update,
        {
            "agent": "agent",
            "finalize": "finalize",
            END: END,
        }
    )

    graph.add_edge("finalize", "agent")

    return graph.compile()
