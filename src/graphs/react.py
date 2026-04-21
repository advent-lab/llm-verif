from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, RemoveMessage
import logging
import json as _json
import shutil
import re as _re
from pathlib import Path

from ..state.schemas import AgentState
from ..config import Config, load_config
from ..utils.design_loader import scan_design_directory, extract_module_header, extract_all_module_headers
from ..utils.tokens import count_message_tokens, format_token_count
from ..utils.token_tracking import extract_usage_from_response, build_token_record, classify_pending_records
from ..utils.agent_logging import log_agent_request, log_agent_response, Colors
from ..utils.event_log import (
    init_event_log, emit, serialize_message, serialize_config, get_git_info,
)
from ..prompts.loader import load_system_prompt, load_functional_system_prompt
from ..tools import get_all_tools, set_tool_config
from ..tools.analysis import get_cumulative_coverage_db, _create_annotated_source
from ._uvm_helpers import prepare_uvm_workdir, build_uvm_prompt_context


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_functional_coverage(state: AgentState) -> float:
    """Get the current functional coverage from state or cumulative report on disk."""
    funcov = state.get("current_functional_coverage", 0.0)
    if funcov > 0.0:
        return funcov

    config = state["config"]
    if not getattr(config, 'uvm_enabled', False):
        return 0.0

    report_path = config.work_dir / "coverage" / "cumulative_functional_coverage.txt"
    if report_path.exists():
        try:
            from ..utils.questasim import parse_functional_coverage_text
            result = parse_functional_coverage_text(report_path)
            return result.get('total_coverage', 0.0)
        except Exception:
            pass
    return 0.0


def _signal_done_accepted(state: AgentState) -> bool:
    """Return True if the agent's signal_done call meets a valid termination condition."""
    config = state["config"]
    if state.get("cumulative_coverage", 0.0) >= 100.0:
        return True
    if getattr(config, 'uvm_enabled', False):
        if getattr(config, 'uvm_coverage_mode', 'functional') == "functional":
            funcov = _get_functional_coverage(state)
            target = getattr(config, 'functional_coverage_target', 100.0)
            if funcov >= target:
                return True
    if state["consecutive_failures"] >= config.max_retries:
        return True
    if state["no_progress_count"] >= config.max_no_progress:
        return True
    if state["api_calls"] >= config.max_iterations:
        return True
    if state["iteration"] > config.max_iterations:
        return True
    return False


def initialize_node(state: AgentState) -> AgentState:
    """
    Initialize node: One-time setup of environment.

    Steps:
    1. Load configuration (dashboard or direct mode)
    2. Create work directory structure
    3. Extract module headers from all design files
    4. Construct system prompt
    """
    logging.info("Initializing workflow")

    # Load config (supports both dashboard and direct modes)
    config = load_config()

    # Create work directory structure
    (config.work_dir / "testbenches").mkdir(parents=True, exist_ok=True)
    (config.work_dir / "logs").mkdir(parents=True, exist_ok=True)
    (config.work_dir / "coverage").mkdir(parents=True, exist_ok=True)

    logging.info(f"Work directory: {config.work_dir}")
    logging.info(f"Design: {config.design_name}")
    logging.info(f"Spec: {config.spec_path.name}")
    logging.info(f"Design files: {[f.name for f in config.design_files]}")
    if config.design_context_files:
        logging.info(f"Context files: {[f.name for f in config.design_context_files]}")

    # Extract module headers from all design files
    module_header = extract_all_module_headers(config.design_files)

    # ── UVM setup: prepare .f file, read context files ────────────────────
    uvm_prompt_kwargs = {}
    if config.uvm_enabled:
        prepare_uvm_workdir(config)
        uvm_prompt_kwargs = build_uvm_prompt_context(config)
        # Store detected names on config for use by validators
        if uvm_prompt_kwargs.get('uvm_interface_name'):
            config.uvm_interface_name = uvm_prompt_kwargs['uvm_interface_name']
        if uvm_prompt_kwargs.get('uvm_env_class'):
            config.uvm_env_class = uvm_prompt_kwargs['uvm_env_class']

    # Construct system prompt (mode-aware)
    if config.uvm_enabled:
        system_prompt = load_system_prompt(
            design_name=config.design_name,
            design_dir=config.design_dir,
            spec_path=config.spec_path,
            design_files=config.design_files,
            design_context_files=config.design_context_files,
            module_header=module_header,
            design_context_enabled=config.design_context_enabled,
            testplan_enabled=config.testplan_enabled,
            max_iterations=config.max_iterations,
            sim_runs=config.sim_runs,
            sim_timeout=config.sim_timeout,
            **uvm_prompt_kwargs,
        )
    elif config.functional_coverage_enabled:
        system_prompt = load_functional_system_prompt(
            design_name=config.design_name,
            design_dir=config.design_dir,
            spec_path=config.spec_path,
            design_files=config.design_files,
            design_context_files=config.design_context_files,
            module_header=module_header,
            design_context_enabled=config.design_context_enabled,
            testbench_template_path=config.functional_coverage_testbench_path,
            coverage_target=config.functional_coverage_target,
            max_iterations=config.max_iterations,
            sim_runs=config.sim_runs,
            sim_timeout=config.sim_timeout
        )
    else:
        system_prompt = load_system_prompt(
            design_name=config.design_name,
            design_dir=config.design_dir,
            spec_path=config.spec_path,
            design_files=config.design_files,
            design_context_files=config.design_context_files,
            module_header=module_header,
            design_context_enabled=config.design_context_enabled,
            testplan_enabled=config.testplan_enabled,
            max_iterations=config.max_iterations,
            sim_runs=config.sim_runs,
            sim_timeout=config.sim_timeout
        )

    # Set config for tools
    config.current_iteration = 1
    config.current_attempt = 1
    set_tool_config(config)

    # Initialize structured JSONL event log
    init_event_log(config.work_dir / "events.jsonl")

    emit("session_start", {
        "config": serialize_config(config),
        "git": get_git_info(),
    })

    emit("system_prompt", {
        "content": system_prompt,
        "content_length": len(system_prompt),
        "module_header": module_header,
    })

    # Choose appropriate initial human message
    if config.uvm_enabled:
        if config.uvm_coverage_mode == "line":
            init_human_msg = (
                "Begin UVM verification. Start by reading the specification. "
                "Then generate UVM sequences and a test file to achieve "
                "maximum line/statement coverage of the RTL design."
            )
        else:
            init_human_msg = (
                "Begin UVM verification. Start by reading the specification. "
                "Then generate UVM sequences and a test file to achieve both "
                "code and functional coverage."
            )
    else:
        init_human_msg = "Begin verification. Start by reading the specification."

    emit("human_message", {
        "source": "init",
        "content": init_human_msg,
    })

    # Initialize state
    return {
        "messages": [
            SystemMessage(content=system_prompt),
            HumanMessage(content=init_human_msg)
        ],
        "config": config,
        "design_name": config.design_name,
        "design_dir": str(config.design_dir),
        "spec_path": str(config.spec_path),
        "design_files": [str(f) for f in config.design_files],
        "design_context_files": [str(f) for f in config.design_context_files],
        "rtl_dir": str(config.design_dir),
        "module_header": module_header,
        "work_dir": str(config.work_dir),
        "iteration": 1,
        "attempt": 1,
        "api_calls": 0,
        "consecutive_failures": 0,
        "no_progress_count": 0,
        "no_tool_call_count": 0,
        "current_coverage": 0.0,
        "max_coverage": 0.0,
        "cumulative_coverage": 0.0,
        "cumulative_coverage_db": None,
        "functional_coverage_enabled": config.functional_coverage_enabled,
        "current_functional_coverage": 0.0,
        "max_functional_coverage": 0.0,
        "uncovered_bins": [],
        # UVM mode
        "uvm_enabled": config.uvm_enabled,
        "uvm_coverage_mode": config.uvm_coverage_mode,
        # Infrastructure modification
        "infra_modification_enabled": False,
        "original_driver_path": (
            str(config.uvm_driver_file) if getattr(config, 'uvm_driver_file', None) else None
        ),
        "is_done": False,
        "done_reason": None,
        "is_finalizing": False,
        "token_usage": []
    }

# Cumulative token counters for token_count events (Codex-style running totals)
_cumulative_tokens = {
    "input_tokens": 0,
    "output_tokens": 0,
    "reasoning_tokens": 0,
    "cached_input_tokens": 0,
    "total_tokens": 0,
}


def agent_node(state: AgentState) -> AgentState:
    """
    Agent node: LLM reasoning and tool selection.
    """
    global _cumulative_tokens

    # Get config from state
    # NOTE: Do NOT reset config.current_attempt here - the tools manage this counter
    # with a "capture then increment" pattern. Resetting it causes log file overwrites.
    config = state["config"]

    # Create LLM
    llm_kwargs = dict(
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        api_key=config.openai_api_key,
    )
    if config.reasoning_effort != "disabled":
        llm_kwargs["reasoning_effort"] = config.reasoning_effort
    llm = ChatOpenAI(**llm_kwargs)

    # Bind tools (mode-aware)
    func_cov = getattr(config, 'functional_coverage_enabled', False)
    tools = get_all_tools(functional_coverage=func_cov)
    llm_with_tools = llm.bind_tools(tools)

    # Increment API call counter before logging so REQUEST and RESPONSE show the same number
    new_api_calls = state.get("api_calls", 0) + 1
    request_state = dict(state)
    request_state["api_calls"] = new_api_calls

    # Log what we're sending to the LLM (before API call)
    log_agent_request(request_state)

    # --- JSONL: api_request event ---
    messages = state.get("messages", [])
    # Serialize latest messages for the event log (last batch of tool results + preceding AI message)
    latest_serialized = []
    for msg in messages[-10:]:
        latest_serialized.append(serialize_message(msg))

    emit("api_request", {
        "api_call": new_api_calls,
        "iteration": state.get("iteration", 1),
        "consecutive_failures": state.get("consecutive_failures", 0),
        "no_progress_count": state.get("no_progress_count", 0),
        "no_tool_call_count": state.get("no_tool_call_count", 0),
        "current_coverage": state.get("current_coverage", 0.0),
        "cumulative_coverage": state.get("cumulative_coverage", 0.0),
        "message_count": len(messages),
        "estimated_input_tokens": count_message_tokens(messages, config.model),
        "latest_messages": latest_serialized,
    })

    # Invoke LLM (this is an API call)
    response = llm_with_tools.invoke(state["messages"])

    # Extract token usage from response (including reasoning + cached tokens)
    usage = extract_usage_from_response(response)

    # --- JSONL: reasoning event ---
    emit("reasoning", {
        "api_call": new_api_calls,
        "content": response.content if hasattr(response, "content") else None,
        "content_length": len(response.content) if hasattr(response, "content") and response.content else 0,
    })

    # Build per-call tool call list for classification
    tool_call_names = []
    tool_call_args = []
    if hasattr(response, 'tool_calls') and response.tool_calls:
        for tc in response.tool_calls:
            tool_call_names.append(tc.get('name', 'unknown'))
            tool_call_args.append(tc.get('args', {}))

    # --- JSONL: tool_call events (one per tool) ---
    if hasattr(response, 'tool_calls') and response.tool_calls:
        for i, tc in enumerate(response.tool_calls):
            emit("tool_call", {
                "api_call": new_api_calls,
                "call_index": i,
                "tool_name": tc.get("name", "unknown"),
                "arguments": tc.get("args", {}),
                "call_id": tc.get("id", ""),
            })

    # --- JSONL: token_count event (per-call + cumulative) ---
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
        "last_usage": last_usage,
        "cumulative_usage": dict(_cumulative_tokens),
        "model_context_window": config.context_window,
    })

    # Build token usage record (category assigned later in update_state_node)
    token_record = build_token_record(
        api_call_num=new_api_calls,
        iteration=state.get("iteration", 1),
        usage=usage,
        tool_calls=tool_call_names,
        tool_call_args=tool_call_args,
        failures=state.get("consecutive_failures", 0),
        cumulative_coverage=state.get("cumulative_coverage", 0.0),
    )

    # Log agent response (same api_calls number as the request)
    log_agent_response(response, request_state, usage)

    # Track consecutive no-tool-call responses
    if hasattr(response, 'tool_calls') and response.tool_calls:
        no_tool_call_count = 0
    else:
        no_tool_call_count = state.get("no_tool_call_count", 0) + 1

    return {
        "messages": [response],
        "api_calls": new_api_calls,
        "no_tool_call_count": no_tool_call_count,
        "token_usage": [token_record]
    }


def _emit_tool_results(state: AgentState) -> None:
    """Emit tool_result events for all recent ToolMessages in state."""
    messages = state.get("messages", [])
    # Gather consecutive ToolMessages from the end of the list
    for msg in reversed(messages[-10:]):
        msg_type = type(msg).__name__
        if msg_type != "ToolMessage":
            break
        # Parse success from content
        success = None
        content = msg.content if hasattr(msg, "content") else ""
        if isinstance(content, str):
            try:
                import json as _json
                parsed = _json.loads(content)
                if isinstance(parsed, dict):
                    success = parsed.get("success")
            except (ValueError, TypeError):
                pass

        emit("tool_result", {
            "tool_name": getattr(msg, "name", None),
            "call_id": getattr(msg, "tool_call_id", None),
            "success": success,
            "content": content,
            "content_length": len(content) if isinstance(content, str) else 0,
        })


def _snapshot_state(state: AgentState, trigger: str, delta: dict) -> dict:
    """Build a full state snapshot for a state_update event."""
    # Merge current state with delta to show the resulting state
    return {
        "trigger": trigger,
        "iteration": delta.get("iteration", state.get("iteration", 1)),
        "api_calls": state.get("api_calls", 0),
        "consecutive_failures": delta.get("consecutive_failures", state.get("consecutive_failures", 0)),
        "no_progress_count": delta.get("no_progress_count", state.get("no_progress_count", 0)),
        "no_tool_call_count": state.get("no_tool_call_count", 0),
        "current_coverage": delta.get("current_coverage", state.get("current_coverage", 0.0)),
        "max_coverage": delta.get("max_coverage", state.get("max_coverage", 0.0)),
        "cumulative_coverage": delta.get("cumulative_coverage", state.get("cumulative_coverage", 0.0)),
        "cumulative_coverage_db": delta.get("cumulative_coverage_db", state.get("cumulative_coverage_db")),
        "is_done": state.get("is_done", False),
        "done_reason": state.get("done_reason"),
        "is_finalizing": state.get("is_finalizing", False),
        "delta": delta,
    }


def update_state_node(state: AgentState) -> AgentState:
    """
    Update state node: Track iterations, attempts, and coverage after tool executions.

    Priority order:
    0. Check run_verification_cycle results (composite tool)
    1. Check compile failures (highest priority - stop immediately)
    2. Check simulation failures
    3. Check coverage improvement/no improvement

    Also classifies any unclassified token usage records.
    """
    config = state["config"]

    # --- JSONL: emit tool_result events for all recent tool outputs ---
    _emit_tool_results(state)

    # Classify any pending unclassified token usage records
    classify_pending_records(state)

    # Helper function to parse tool result from message content
    def parse_tool_result(content):
        if isinstance(content, str):
            import json
            try:
                return json.loads(content)
            except:
                return {}
        return content if isinstance(content, dict) else {}

    def _emit_and_return(trigger: str, delta: dict) -> dict:
        """Emit state_update event and return the delta."""
        emit("state_update", _snapshot_state(state, trigger, delta))
        return delta

    # Priority 0: Check for run_verification_cycle results (composite tool)
    latest_msg = state["messages"][-1] if state["messages"] else None
    if latest_msg and hasattr(latest_msg, 'name') and latest_msg.name == 'run_verification_cycle':
        result = parse_tool_result(latest_msg.content)
        stopped_at = result.get("stopped_at")

        if not result.get("success", False):
            # Failed at some stage
            if stopped_at in ("compile", "simulate"):
                sub_result = result.get(f"{stopped_at}_result", {})
                iter_num = sub_result.get("iteration", "?")
                retry_num = sub_result.get("retry", "?")
                logging.warning(
                    f"Verification cycle failed at {stopped_at} "
                    f"(iter {iter_num}, retry {retry_num})"
                )
                return _emit_and_return(f"verification_cycle_{stopped_at}_fail", {
                    "consecutive_failures": state["consecutive_failures"] + 1
                })
            # Write or coverage failure — no state change, agent sees the error
            logging.warning(f"Verification cycle failed at {stopped_at} stage")
            return _emit_and_return(f"verification_cycle_{stopped_at}_fail", {})
        else:
            # Full success — mirror parse_coverage / parse_functional_coverage success logic
            coverage_result = result.get("coverage_result", {})
            func_cov_enabled = getattr(config, 'functional_coverage_enabled', False)
            cumulative_coverage = coverage_result.get(
                "cumulative_coverage", coverage_result.get("total_coverage", 0.0)
            )
            cumulative_db = coverage_result.get("cumulative_coverage_db")
            next_iteration = state["iteration"] + 1

            config.current_iteration = next_iteration

            if func_cov_enabled:
                prev_cumulative = state.get("current_functional_coverage", 0.0)
                uncovered_bins = coverage_result.get("uncovered_bins", [])
            else:
                prev_cumulative = state.get("cumulative_coverage", 0.0)
                iteration_coverage = coverage_result.get(
                    "iteration_coverage", coverage_result.get("total_coverage", 0.0)
                )

            if cumulative_coverage > prev_cumulative:
                logging.info(
                    f"{'Functional c' if func_cov_enabled else 'C'}overage improved: "
                    f"{prev_cumulative:.2f}% → {cumulative_coverage:.2f}%"
                )
                delta = {
                    "current_coverage": cumulative_coverage,
                    "max_coverage": max(state.get("max_coverage", 0.0), cumulative_coverage),
                    "cumulative_coverage": cumulative_coverage,
                    "cumulative_coverage_db": cumulative_db,
                    "iteration": next_iteration,
                    "consecutive_failures": 0,
                    "no_progress_count": 0,
                }
                if func_cov_enabled:
                    delta["current_functional_coverage"] = cumulative_coverage
                    delta["max_functional_coverage"] = max(state.get("max_functional_coverage", 0.0), cumulative_coverage)
                    delta["uncovered_bins"] = uncovered_bins
                else:
                    delta["current_coverage"] = iteration_coverage
                    delta["max_coverage"] = max(state.get("max_coverage", 0.0), iteration_coverage)
                return _emit_and_return("verification_cycle_coverage_improved", delta)
            else:
                logging.warning(
                    f"No {'functional ' if func_cov_enabled else ''}coverage improvement: {cumulative_coverage:.2f}%"
                )
                delta = {
                    "cumulative_coverage": cumulative_coverage,
                    "cumulative_coverage_db": cumulative_db,
                    "iteration": next_iteration,
                    "consecutive_failures": 0,
                    "no_progress_count": state["no_progress_count"] + 1,
                }
                if func_cov_enabled:
                    delta["current_functional_coverage"] = cumulative_coverage
                    delta["uncovered_bins"] = coverage_result.get("uncovered_bins", [])
                    delta["current_coverage"] = cumulative_coverage
                else:
                    delta["current_coverage"] = iteration_coverage
                return _emit_and_return("verification_cycle_no_improvement", delta)

    # Priority 0b: request_infra_modification → enable infra mod in state
    for msg in reversed(state["messages"][-5:]):
        if hasattr(msg, 'name') and msg.name == 'request_infra_modification':
            result = parse_tool_result(msg.content)
            if result.get('infra_modification_granted'):
                if not state.get("infra_modification_enabled", False):
                    logging.info(
                        f"{Colors.MAGENTA}INFRASTRUCTURE MODIFICATION GRANTED{Colors.RESET}"
                    )
                return _emit_and_return("infra_mod_granted", {"infra_modification_enabled": True})
            break

    # Priority 1: Check for compile_design failures
    for msg in reversed(state["messages"][-5:]):
        if hasattr(msg, 'name') and msg.name == 'compile_design':
            result = parse_tool_result(msg.content)

            # NOTE: Do NOT sync config.current_attempt from tool result here.
            # The tools use a "capture then increment" pattern - the result contains
            # the value USED, not the incremented value. Syncing would reset the counter.

            if not result.get('success', False):
                # Compilation failed - increment consecutive_failures
                iter_num = result.get('iteration', '?')
                retry_num = result.get('retry', '?')
                logging.warning(f"Compilation failed (iter {iter_num}, retry {retry_num})")
                return _emit_and_return("compile_fail", {
                    "consecutive_failures": state["consecutive_failures"] + 1
                })
            break  # Found compile result, move to next check

    # Priority 2: Check for run_simulation failures
    for msg in reversed(state["messages"][-5:]):
        if hasattr(msg, 'name') and msg.name == 'run_simulation':
            result = parse_tool_result(msg.content)

            if not result.get('success', False):
                # Simulation failed - increment consecutive_failures
                iter_num = result.get('iteration', '?')
                retry_num = result.get('retry', '?')
                logging.warning(f"Simulation failed (iter {iter_num}, retry {retry_num})")
                return _emit_and_return("sim_fail", {
                    "consecutive_failures": state["consecutive_failures"] + 1
                })
            break  # Found sim result, move to next check

    # Priority 3a: Check for parse_functional_coverage results
    latest_msg = state["messages"][-1] if state["messages"] else None
    if latest_msg and hasattr(latest_msg, 'name') and latest_msg.name == 'parse_functional_coverage':
        result = parse_tool_result(latest_msg.content)

        if result.get('success'):
            cumulative_coverage = result.get('cumulative_coverage', result.get('total_coverage', 0.0))
            cumulative_db = result.get('cumulative_coverage_db')
            uncovered_bins = result.get('uncovered_bins', [])
            next_iteration = state["iteration"] + 1

            config.current_iteration = next_iteration
            prev_cumulative = state.get("current_functional_coverage", 0.0)

            if cumulative_coverage > prev_cumulative:
                logging.info(f"Functional coverage improved: {prev_cumulative:.2f}% → {cumulative_coverage:.2f}%")
                return _emit_and_return("func_coverage_improved", {
                    "current_coverage": cumulative_coverage,
                    "max_coverage": max(state.get("max_coverage", 0.0), cumulative_coverage),
                    "cumulative_coverage": cumulative_coverage,
                    "cumulative_coverage_db": cumulative_db,
                    "current_functional_coverage": cumulative_coverage,
                    "max_functional_coverage": max(state.get("max_functional_coverage", 0.0), cumulative_coverage),
                    "uncovered_bins": uncovered_bins,
                    "iteration": next_iteration,
                    "consecutive_failures": 0,
                    "no_progress_count": 0,
                })
            else:
                logging.warning(f"No functional coverage improvement: {cumulative_coverage:.2f}%")
                return _emit_and_return("func_no_improvement", {
                    "current_coverage": cumulative_coverage,
                    "cumulative_coverage": cumulative_coverage,
                    "cumulative_coverage_db": cumulative_db,
                    "current_functional_coverage": cumulative_coverage,
                    "uncovered_bins": uncovered_bins,
                    "iteration": next_iteration,
                    "consecutive_failures": 0,
                    "no_progress_count": state["no_progress_count"] + 1,
                })

    # Priority 3b: Check for parse_coverage results (coverage improvement tracking)
    # IMPORTANT: Only check the LATEST message to avoid re-processing old parse_coverage results
    # which would cause false no_progress_count increments after every tool call
    latest_msg = state["messages"][-1] if state["messages"] else None
    if latest_msg and hasattr(latest_msg, 'name') and latest_msg.name == 'parse_coverage':
        result = parse_tool_result(latest_msg.content)

        if result.get('success'):
            # Get both iteration and cumulative coverage
            iteration_coverage = result.get('iteration_coverage', result.get('total_coverage', 0.0))
            cumulative_coverage = result.get('cumulative_coverage', result.get('total_coverage', 0.0))
            cumulative_db = result.get('cumulative_coverage_db')
            next_iteration = state["iteration"] + 1

            # Always increment iteration after successful parse_coverage
            # This ensures log files correlate with testbench iterations
            # "No progress" is NOT a retry - it's a successful cycle that didn't improve coverage
            config.current_iteration = next_iteration

            # Use CUMULATIVE coverage for progress tracking
            # This ensures we detect progress even if individual testbenches cover different areas
            prev_cumulative = state.get("cumulative_coverage", 0.0)

            # Check if cumulative coverage improved
            if cumulative_coverage > prev_cumulative:
                logging.info(f"Cumulative coverage improved: {prev_cumulative:.2f}% → {cumulative_coverage:.2f}% (this iteration: {iteration_coverage:.2f}%)")
                return _emit_and_return("coverage_improved", {
                    "current_coverage": iteration_coverage,
                    "max_coverage": max(state["max_coverage"], iteration_coverage),
                    "cumulative_coverage": cumulative_coverage,
                    "cumulative_coverage_db": cumulative_db,
                    "iteration": next_iteration,
                    "consecutive_failures": 0,  # Reset on improvement
                    "no_progress_count": 0  # Reset no_progress on improvement
                })
            else:
                logging.warning(f"No cumulative coverage improvement: {cumulative_coverage:.2f}% (this iteration: {iteration_coverage:.2f}%)")
                return _emit_and_return("no_improvement", {
                    "current_coverage": iteration_coverage,
                    "cumulative_coverage": cumulative_coverage,  # Update even if no improvement
                    "cumulative_coverage_db": cumulative_db,
                    "iteration": next_iteration,  # Still increment iteration
                    "consecutive_failures": 0,  # Reset - cycle was successful
                    "no_progress_count": state["no_progress_count"] + 1  # Track for early termination
                })

    # No updates needed
    return _emit_and_return("none", {})

def finalize_node(state: AgentState) -> AgentState:
    """
    Finalize node: Inject a message telling the agent to write its final report.

    Called when the framework detects a termination condition (coverage complete
    or no progress). Gives the agent one last turn to write report.md.
    """
    config = state["config"]
    cumulative_coverage = state.get("cumulative_coverage", 0.0)
    no_progress = state.get("no_progress_count", 0)
    no_tool_calls = state.get("no_tool_call_count", 0)
    iteration = state.get("iteration", 0)

    # Determine termination reason from state
    api_calls = state.get("api_calls", 0)
    consecutive_failures = state.get("consecutive_failures", 0)
    token_count = count_message_tokens(state["messages"], config.model)

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
    elif iteration > config.max_iterations:
        reason = "max_iterations"
    elif consecutive_failures >= config.max_retries:
        reason = "max_retries"
    elif no_tool_calls >= config.max_no_tool_calls:
        reason = "no_tool_calls"
    elif no_progress >= config.max_no_progress:
        reason = "no_progress"
    else:
        reason = "unknown"

    # Parse latest coverage data for the report
    missed_coverage_info = ""
    if func_cov_enabled:
        uncovered_bins = state.get("uncovered_bins", [])
        if uncovered_bins:
            bin_lines = [f"- {b.get('covergroup', '?')}.{b.get('coverpoint', '?')}: `{b.get('bin_name', '?')}`"
                         for b in uncovered_bins[:20]]
            missed_coverage_info = f"\n\n## Still Uncovered Bins\n\n" + "\n".join(bin_lines)
    else:
        cumulative_db = get_cumulative_coverage_db()
        if cumulative_db and Path(cumulative_db).exists():
            try:
                from ..tools.analysis import _adapter as coverage_adapter
                if coverage_adapter is not None:
                    cumulative_result = coverage_adapter.parse_coverage(Path(cumulative_db))
                    annotated = _create_annotated_source(cumulative_result.uncovered_lines)
                    if annotated:
                        missed_coverage_info = f"\n\n## Latest Missed Coverage\n\n{annotated}"
            except Exception as e:
                logging.warning(f"Failed to parse coverage in finalize: {e}")

    if func_cov_enabled:
        cov_line = f"Final functional coverage: {effective_coverage:.2f}%."
        report_note = (
            "The report MUST list all remaining uncovered bins and explain what stimulus "
            "would be needed to close each one."
        )
    else:
        cov_line = f"Final cumulative coverage: {cumulative_coverage:.2f}%."
        report_note = (
            "The report MUST classify ALL remaining uncovered lines by category "
            "(unreachable, excludable, potential bugs, needs more effort). "
            "Follow the report requirements from your instructions (Step 7)."
        )

    finalize_message = (
        f"FRAMEWORK NOTICE: Verification terminated (reason: {reason}). "
        f"{cov_line} "
        f"Iterations completed: {iteration - 1}.\n\n"
        f"You MUST now write your final run report to `report.md` using `write_file`. "
        f"This is your LAST turn — only `write_file` tool calls will be executed. "
        f"Do NOT call any analysis tools, `read_file`, or other tools. "
        f"If you need additional context you haven't already gathered, note it under "
        f"'Next Steps' in your report.\n\n"
        f"{report_note}"
        f"{missed_coverage_info}"
    )

    logging.info(f"{Colors.MAGENTA}{Colors.BOLD}{'='*80}{Colors.RESET}")
    logging.info(f"{Colors.MAGENTA}{Colors.BOLD}FINALIZE ({reason}): Giving agent one last turn to write report.md{Colors.RESET}")
    logging.info(f"{Colors.MAGENTA}Cumulative coverage: {cumulative_coverage:.2f}% | No-progress count: {no_progress} | No-tool-call count: {no_tool_calls}{Colors.RESET}")
    logging.info(f"{Colors.MAGENTA}{'='*80}{Colors.RESET}\n")

    # --- JSONL: finalize + human_message events ---
    emit("finalize", {
        "reason": reason,
        "cumulative_coverage": cumulative_coverage,
        "iterations_completed": iteration - 1,
        "no_progress_count": no_progress,
        "no_tool_call_count": no_tool_calls,
    })

    emit("human_message", {
        "source": "finalize",
        "content": finalize_message,
    })

    return {
        "messages": [HumanMessage(content=finalize_message)],
        "is_finalizing": True,
        "done_reason": reason
    }


def _find_ai_message_for_tool(messages, tool_call_id):
    """Find the AIMessage whose tool_calls contains the given tool_call_id."""
    for msg in reversed(messages):
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.get('id') == tool_call_id:
                    return msg
    return None


def _all_tool_calls_are(ai_msg, tool_name: str) -> bool:
    """Return True only if ALL tool_calls in the AIMessage are for the given tool name."""
    if not hasattr(ai_msg, 'tool_calls') or not ai_msg.tool_calls:
        return False
    return all(tc.get('name') == tool_name for tc in ai_msg.tool_calls)


def _parse_tool_content(content) -> dict:
    """Parse ToolMessage content into a dict."""
    if isinstance(content, str):
        try:
            return _json.loads(content)
        except (ValueError, TypeError):
            return {}
    return content if isinstance(content, dict) else {}


def prune_verification_cycles(state: AgentState) -> dict:
    """Remove old failed run_verification_cycle message pairs from context.

    Policy:
    - Success pairs (coverage feedback): KEEP all
    - Failure pairs (compile/sim errors): keep only latest N (from config.keep_latest_failures)

    Removes both the AIMessage (with large testbench_content in tool_calls args)
    and its ToolMessage (with error feedback) to maintain valid conversation structure.
    """
    config = state["config"]
    keep_n = config.keep_latest_failures
    messages = state["messages"]

    # Find all run_verification_cycle ToolMessages that are failures
    failure_tool_msgs = []
    for msg in messages:
        if not (hasattr(msg, 'name') and msg.name == 'run_verification_cycle'):
            continue
        result = _parse_tool_content(msg.content)
        if not result.get("success", False):
            failure_tool_msgs.append(msg)

    # Nothing to prune?
    if len(failure_tool_msgs) <= keep_n:
        return {}

    # Identify old failure pairs to remove (keep the latest keep_n)
    to_prune = failure_tool_msgs[:-keep_n]
    remove_msgs = []

    for tool_msg in to_prune:
        # Remove the ToolMessage
        remove_msgs.append(RemoveMessage(id=tool_msg.id))

        # Find and remove the corresponding AIMessage (only if it exclusively
        # called run_verification_cycle — avoid orphaning other tool results)
        ai_msg = _find_ai_message_for_tool(messages, tool_msg.tool_call_id)
        if ai_msg and _all_tool_calls_are(ai_msg, "run_verification_cycle"):
            remove_msgs.append(RemoveMessage(id=ai_msg.id))

    if remove_msgs:
        logging.info(
            f"Context pruning: removing {len(to_prune)} old failed verification cycle pair(s) "
            f"({len(remove_msgs)} messages total, keeping latest {keep_n} failure(s))"
        )
        emit("context_prune", {
            "pairs_removed": len(to_prune),
            "messages_removed": len(remove_msgs),
            "policy": "remove_old_failures",
            "kept_latest_failures": keep_n,
        })

    return {"messages": remove_msgs} if remove_msgs else {}


def create_react_graph() -> StateGraph:
    """
    Create the ReAct agent graph.
    """
    # Create graph
    graph = StateGraph(AgentState)

    # Build a combined tool list that supports both coverage modes
    # (the agent only binds the relevant subset, but ToolNode must know all tools)
    from ..tools.analysis import parse_functional_coverage as _pfc
    _all_tools = get_all_tools(functional_coverage=False) + ([_pfc] if _pfc is not None else [])

    # Add nodes
    graph.add_node("initialize", initialize_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(_all_tools))
    graph.add_node("update_state", update_state_node)

    # Add edges
    graph.set_entry_point("initialize")
    graph.add_edge("initialize", "agent")

    # Conditional routing from agent
    def route_after_agent(state: AgentState) -> Literal["tools", "agent", "finalize", END]:
        """Route after agent decision."""
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

        # In finalize mode: only allow write_file tool calls, then END
        if state.get("is_finalizing", False):
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                write_calls = [tc for tc in last_message.tool_calls if tc.get('name') == 'write_file']
                if write_calls:
                    last_message.tool_calls = write_calls
                    return _route("tools", "finalize: executing write_file")
                # Non-write_file tool calls must still flush through tools
                return _route("tools", "finalize: flush non-write_file tool calls")
            return _route(END, "finalize: no write_file call, ending")

        # ── Handle signal_done tool call ────────────────────────────────────
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            for tool_call in last_message.tool_calls:
                if tool_call.get('name') == 'signal_done':
                    reason = tool_call.get('args', {}).get('reason', 'unknown')
                    logging.info(f"Agent called signal_done with reason: {reason}")

                    if reason == "coverage_complete":
                        cumulative_cov = state.get("cumulative_coverage", 0.0)
                        funcov = _get_functional_coverage(state)
                        funcov_target = getattr(config, 'functional_coverage_target', 100.0)
                        uvm_mode = getattr(config, 'uvm_enabled', False)
                        uvm_cov_mode = getattr(config, 'uvm_coverage_mode', 'functional')
                        if cumulative_cov >= 100.0 or (
                            uvm_mode and uvm_cov_mode == "functional" and funcov >= funcov_target
                        ):
                            logging.info(
                                f"✓ Accepting signal_done: coverage target met! "
                                f"(code={cumulative_cov:.1f}%, funcov={funcov:.1f}%)"
                            )
                            return _route("finalize", "signal_done: coverage_complete")
                        else:
                            logging.warning(
                                f"⚠️  Agent claimed coverage_complete but coverage is "
                                f"{cumulative_cov:.1f}%"
                            )

                    if _signal_done_accepted(state):
                        logging.info(f"✓ Accepting signal_done: {reason}")
                        return _route("finalize", f"signal_done: {reason}")
                    else:
                        # Increment no_progress_count so repeated signal_done
                        # calls eventually trigger termination.
                        state["no_progress_count"] = state.get("no_progress_count", 0) + 1
                        logging.warning(
                            f"⚠️  REJECTING signal_done: termination conditions not met\n"
                            f"   no_progress_count: {state['no_progress_count']}/{config.max_no_progress}\n"
                            f"   api_calls: {state['api_calls']}/{config.max_iterations}"
                        )
                        break  # Fall through to normal tool processing

        # ── Check hard termination conditions ──────────────────────────────
        if state["api_calls"] >= config.max_iterations:
            logging.info(f"Max API calls reached: {state['api_calls']}/{config.max_iterations} — routing to finalize")
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                return _route("tools", "hard_termination_flush_pending_tools")
            return _route("finalize", f"max_api_calls ({state['api_calls']}/{config.max_iterations})")

        if state["iteration"] > config.max_iterations:
            logging.info(f"Max coverage iterations reached: {state['iteration']}/{config.max_iterations} — routing to finalize")
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                return _route("tools", "hard_termination_flush_pending_tools")
            return _route("finalize", f"max_iterations ({state['iteration']}/{config.max_iterations})")

        if state["consecutive_failures"] >= config.max_retries:
            logging.info(f"Max retries reached — routing to finalize")
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                return _route("tools", "hard_termination_flush_pending_tools")
            return _route("finalize", f"max_retries ({state['consecutive_failures']}/{config.max_retries})")

        if state["no_progress_count"] >= config.max_no_progress:
            logging.info(f"No progress after {state['no_progress_count']} attempts — routing to finalize")
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                return _route("tools", "hard_termination_flush_pending_tools")
            return _route("finalize", f"max_no_progress ({state['no_progress_count']}/{config.max_no_progress})")

        # Check context window limit
        token_count = count_message_tokens(state["messages"], config.model)
        if token_count >= config.context_window:
            logging.info(f"Context window limit reached: {format_token_count(token_count, config.context_window)} — routing to finalize")
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                return _route("tools", "hard_termination_flush_pending_tools")
            return _route("finalize", f"context_window_limit ({token_count:,}/{config.context_window:,})")

        # Route to tools if tool calls present
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            tool_names = [tc.get('name', '?') for tc in last_message.tool_calls]
            return _route("tools", f"tool_calls: {tool_names}")

        # No tool calls — check if agent is stuck in reasoning-only loop
        if state.get("no_tool_call_count", 0) >= config.max_no_tool_calls:
            logging.info(f"Agent returned {state['no_tool_call_count']} consecutive responses with no tool calls — routing to finalize")
            return _route("finalize", f"max_no_tool_calls ({state['no_tool_call_count']}/{config.max_no_tool_calls})")

        # Otherwise loop back so agent tries again
        return _route("agent", "no_tool_calls, retrying")

    graph.add_conditional_edges(
        "agent",
        route_after_agent,
        {
            "tools": "tools",
            "agent": "agent",
            "finalize": "finalize",
            END: END
        }
    )

    # After tools, update state, prune old messages, then check termination
    graph.add_edge("tools", "update_state")
    graph.add_node("prune_context", prune_verification_cycles)
    graph.add_edge("update_state", "prune_context")

    # Finalize node: injects message for agent to write report, then routes to agent
    graph.add_node("finalize", finalize_node)
    graph.add_edge("finalize", "agent")

    def route_after_update(state: AgentState) -> Literal["agent", "finalize", END]:
        """Route after state update - check termination conditions with updated state."""
        config = state["config"]
        is_finalizing = state.get("is_finalizing", False)

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

        # If already finalizing, the agent had its last turn — end now
        if is_finalizing:
            logging.info("Finalize turn complete — ending run")
            return _route(END, "finalize_turn_complete")

        # Coverage complete: route to finalize so agent can write report
        cumulative = state.get("cumulative_coverage", 0.0)
        func_cov_enabled = getattr(config, 'functional_coverage_enabled', False)
        if func_cov_enabled:
            cumulative = state.get("current_functional_coverage", 0.0)
            target = getattr(config, 'functional_coverage_target', 100.0)
        else:
            target = 100.0
        if cumulative >= target:
            logging.info(f"{'Functional c' if func_cov_enabled else 'C'}overage complete ({cumulative:.2f}% >= {target:.1f}%) — routing to finalize")
            return _route("finalize", f"coverage_complete ({cumulative:.2f}%)")

        # Check termination conditions with UPDATED state — route to finalize so agent writes report.md
        if state["api_calls"] >= config.max_iterations:
            logging.info(f"Max API calls reached: {state['api_calls']}/{config.max_iterations} — routing to finalize")
            return _route("finalize", f"max_api_calls ({state['api_calls']}/{config.max_iterations})")

        if state["iteration"] > config.max_iterations:
            logging.info(f"Max coverage iterations reached: {state['iteration']}/{config.max_iterations} — routing to finalize")
            return _route("finalize", f"max_iterations ({state['iteration']}/{config.max_iterations})")

        if state["consecutive_failures"] >= config.max_retries:
            logging.info(f"Max retries reached: {state['consecutive_failures']}/{config.max_retries} — routing to finalize")
            return _route("finalize", f"max_retries ({state['consecutive_failures']}/{config.max_retries})")

        # No-progress: route to finalize so agent can write report
        if state["no_progress_count"] >= config.max_no_progress:
            logging.info(f"No progress after {state['no_progress_count']} attempts (MAX_NO_PROGRESS={config.max_no_progress}) - cumulative coverage stuck at {state.get('cumulative_coverage', 0.0):.2f}% — routing to finalize")
            return _route("finalize", f"max_no_progress ({state['no_progress_count']}/{config.max_no_progress})")

        # Check context window limit
        token_count = count_message_tokens(state["messages"], config.model)
        if token_count >= config.context_window:
            logging.info(f"Context window limit reached: {format_token_count(token_count, config.context_window)} (CONTEXT_WINDOW={config.context_window:,}) — routing to finalize")
            return _route("finalize", f"context_window_limit ({token_count:,}/{config.context_window:,})")

        # Continue to agent
        return _route("agent", "continue")

    graph.add_conditional_edges(
        "prune_context",
        route_after_update,
        {
            "agent": "agent",
            "finalize": "finalize",
            END: END
        }
    )

    return graph.compile()
