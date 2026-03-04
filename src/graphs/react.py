from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import logging
from pathlib import Path

from ..state.schemas import AgentState
from ..config import Config, load_config
from ..utils.design_loader import scan_design_directory, extract_module_header, extract_all_module_headers
from ..utils.tokens import count_message_tokens, format_token_count
from ..utils.token_tracking import extract_usage_from_response, build_token_record, classify_pending_records
from ..utils.agent_logging import log_agent_request, log_agent_response, Colors
from ..prompts.loader import load_system_prompt
from ..tools import get_all_tools, set_tool_config

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

    # Construct system prompt
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
    config.current_iteration = 1  # Start at iteration 1
    config.current_attempt = 1  # Start at attempt 1
    set_tool_config(config)

    # Initialize state
    return {
        "messages": [
            SystemMessage(content=system_prompt),
            HumanMessage(content="Begin verification. Start by reading the specification.")
        ],
        "config": config,  # Store config in state to avoid repeated loading
        "design_name": config.design_name,
        "design_dir": str(config.design_dir),
        "spec_path": str(config.spec_path),
        "design_files": [str(f) for f in config.design_files],
        "design_context_files": [str(f) for f in config.design_context_files],
        "rtl_dir": str(config.design_dir),  # Deprecated, kept for compatibility
        "module_header": module_header,
        "work_dir": str(config.work_dir),
        "iteration": 1,
        "attempt": 1,
        "api_calls": 0,
        "consecutive_failures": 0,
        "no_progress_count": 0,
        "current_coverage": 0.0,
        "max_coverage": 0.0,
        "cumulative_coverage": 0.0,
        "cumulative_coverage_db": None,
        "is_done": False,
        "done_reason": None,
        "is_finalizing": False,
        "token_usage": []
    }

def agent_node(state: AgentState) -> AgentState:
    """
    Agent node: LLM reasoning and tool selection.
    """
    # Get config from state
    # NOTE: Do NOT reset config.current_attempt here - the tools manage this counter
    # with a "capture then increment" pattern. Resetting it causes log file overwrites.
    config = state["config"]

    # Create LLM
    llm = ChatOpenAI(
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        api_key=config.openai_api_key
    )

    # Bind tools
    tools = get_all_tools()
    llm_with_tools = llm.bind_tools(tools)

    # Log what we're sending to the LLM (before API call)
    log_agent_request(state)

    # Invoke LLM (this is an API call)
    response = llm_with_tools.invoke(state["messages"])

    # Increment API call counter
    new_api_calls = state.get("api_calls", 0) + 1

    # Extract token usage from response (including reasoning + cached tokens)
    usage = extract_usage_from_response(response)

    # Build per-call tool call list for classification
    tool_call_names = []
    tool_call_args = []
    if hasattr(response, 'tool_calls') and response.tool_calls:
        for tc in response.tool_calls:
            tool_call_names.append(tc.get('name', 'unknown'))
            tool_call_args.append(tc.get('args', {}))

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

    # Log agent response (with updated api_calls)
    temp_state = dict(state)
    temp_state["api_calls"] = new_api_calls
    log_agent_response(response, temp_state, usage)

    return {
        "messages": [response],
        "api_calls": new_api_calls,
        "token_usage": [token_record]
    }


def update_state_node(state: AgentState) -> AgentState:
    """
    Update state node: Track iterations, attempts, and coverage after tool executions.

    Priority order:
    1. Check compile failures (highest priority - stop immediately)
    2. Check simulation failures
    3. Check coverage improvement/no improvement

    Also classifies any unclassified token usage records.
    """
    config = state["config"]

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
                return {
                    "consecutive_failures": state["consecutive_failures"] + 1
                }
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
                return {
                    "consecutive_failures": state["consecutive_failures"] + 1
                }
            break  # Found sim result, move to next check

    # Priority 3: Check for parse_coverage results (coverage improvement tracking)
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
                logging.info(f"Cumulative coverage improved: {prev_cumulative:.1f}% → {cumulative_coverage:.1f}% (this iteration: {iteration_coverage:.1f}%)")
                return {
                    "current_coverage": iteration_coverage,
                    "max_coverage": max(state["max_coverage"], iteration_coverage),
                    "cumulative_coverage": cumulative_coverage,
                    "cumulative_coverage_db": cumulative_db,
                    "iteration": next_iteration,
                    "consecutive_failures": 0,  # Reset on improvement
                    "no_progress_count": 0  # Reset no_progress on improvement
                }
            else:
                logging.warning(f"No cumulative coverage improvement: {cumulative_coverage:.1f}% (this iteration: {iteration_coverage:.1f}%)")
                return {
                    "current_coverage": iteration_coverage,
                    "cumulative_coverage": cumulative_coverage,  # Update even if no improvement
                    "cumulative_coverage_db": cumulative_db,
                    "iteration": next_iteration,  # Still increment iteration
                    "consecutive_failures": 0,  # Reset - cycle was successful
                    "no_progress_count": state["no_progress_count"] + 1  # Track for early termination
                }

    # No updates needed
    return {}

def finalize_node(state: AgentState) -> AgentState:
    """
    Finalize node: Inject a message telling the agent to write its final report.

    Called when the framework detects a termination condition (coverage complete
    or no progress). Gives the agent one last turn to write report.md.
    """
    cumulative_coverage = state.get("cumulative_coverage", 0.0)
    no_progress = state.get("no_progress_count", 0)
    iteration = state.get("iteration", 0)

    if cumulative_coverage >= 100.0:
        reason = "coverage_complete"
        finalize_message = (
            f"FRAMEWORK NOTICE: 100% coverage achieved. "
            f"Iterations completed: {iteration - 1}.\n\n"
            f"Write your final run report to `report.md` using `write_file`. "
            f"Follow the report requirements from your instructions (Step 7)."
        )
    else:
        reason = "no_progress"
        finalize_message = (
            f"FRAMEWORK NOTICE: Verification terminated — no cumulative coverage improvement "
            f"after {no_progress} consecutive iterations. "
            f"Final cumulative coverage: {cumulative_coverage:.1f}%. "
            f"Iterations completed: {iteration - 1}.\n\n"
            f"Write your final run report to `report.md` using `write_file`. "
            f"The report MUST classify ALL remaining uncovered lines by category "
            f"(unreachable, excludable, potential bugs, needs more effort). "
            f"Follow the report requirements from your instructions (Step 7)."
        )

    logging.info(f"{Colors.MAGENTA}{Colors.BOLD}{'='*80}{Colors.RESET}")
    logging.info(f"{Colors.MAGENTA}{Colors.BOLD}FINALIZE ({reason}): Giving agent one last turn to write report.md{Colors.RESET}")
    logging.info(f"{Colors.MAGENTA}Cumulative coverage: {cumulative_coverage:.1f}% | No-progress count: {no_progress}{Colors.RESET}")
    logging.info(f"{Colors.MAGENTA}{'='*80}{Colors.RESET}\n")

    return {
        "messages": [HumanMessage(content=finalize_message)],
        "is_finalizing": True,
        "done_reason": reason
    }


def create_react_graph() -> StateGraph:
    """
    Create the ReAct agent graph.
    """
    # Create graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("initialize", initialize_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(get_all_tools()))
    graph.add_node("update_state", update_state_node)

    # Add edges
    graph.set_entry_point("initialize")
    graph.add_edge("initialize", "agent")

    # Conditional routing from agent
    def route_after_agent(state: AgentState) -> Literal["tools", "agent", END]:
        """Route after agent decision."""
        config = state["config"]
        last_message = state["messages"][-1]

        # In finalize mode: let tool calls execute (so write_file runs), then END
        if state.get("is_finalizing", False):
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                return "tools"
            return END

        # Check termination conditions
        if state["api_calls"] >= config.max_iterations:
            logging.info(f"Max API calls reached: {state['api_calls']}/{config.max_iterations}")
            return END

        if state["iteration"] > config.max_iterations:
            logging.info(f"Max coverage iterations reached: {state['iteration']}/{config.max_iterations}")
            return END

        if state["consecutive_failures"] >= config.max_retries:
            logging.info("Max retries reached")
            return END

        if state["no_progress_count"] >= config.max_no_progress:
            logging.info(f"No progress after {state['no_progress_count']} attempts (MAX_NO_PROGRESS={config.max_no_progress}) - cumulative coverage stuck at {state.get('cumulative_coverage', 0.0):.1f}%")
            return END

        # Check context window limit
        token_count = count_message_tokens(state["messages"], config.model)
        if token_count >= config.context_window:
            logging.info(f"Context window limit reached: {format_token_count(token_count, config.context_window)} (CONTEXT_WINDOW={config.context_window:,})")
            return END

        # Route to tools if tool calls present
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"

        # No tool calls — loop back so agent tries again
        return "agent"

    graph.add_conditional_edges(
        "agent",
        route_after_agent,
        {
            "tools": "tools",
            "agent": "agent",
            END: END
        }
    )

    # After tools, update state then check termination
    graph.add_edge("tools", "update_state")

    # Finalize node: injects message for agent to write report, then routes to agent
    graph.add_node("finalize", finalize_node)
    graph.add_edge("finalize", "agent")

    def route_after_update(state: AgentState) -> Literal["agent", "finalize", END]:
        """Route after state update - check termination conditions with updated state."""
        config = state["config"]
        is_finalizing = state.get("is_finalizing", False)

        # If already finalizing, the agent had its last turn — end now
        if is_finalizing:
            logging.info("Finalize turn complete — ending run")
            return END

        # Coverage complete: route to finalize so agent can write report
        cumulative = state.get("cumulative_coverage", 0.0)
        if cumulative >= 100.0:
            logging.info(f"Coverage complete ({cumulative:.1f}%) — routing to finalize")
            return "finalize"

        # Check termination conditions with UPDATED state
        if state["api_calls"] >= config.max_iterations:
            logging.info(f"Max API calls reached: {state['api_calls']}/{config.max_iterations}")
            return END

        if state["iteration"] > config.max_iterations:
            logging.info(f"Max coverage iterations reached: {state['iteration']}/{config.max_iterations}")
            return END

        if state["consecutive_failures"] >= config.max_retries:
            logging.info(f"Max retries reached: {state['consecutive_failures']}/{config.max_retries}")
            return END

        # No-progress: route to finalize so agent can write report
        if state["no_progress_count"] >= config.max_no_progress:
            logging.info(f"No progress after {state['no_progress_count']} attempts (MAX_NO_PROGRESS={config.max_no_progress}) - cumulative coverage stuck at {state.get('cumulative_coverage', 0.0):.1f}% — routing to finalize")
            return "finalize"

        # Check context window limit
        token_count = count_message_tokens(state["messages"], config.model)
        if token_count >= config.context_window:
            logging.info(f"Context window limit reached: {format_token_count(token_count, config.context_window)} (CONTEXT_WINDOW={config.context_window:,})")
            return END

        # Continue to agent
        return "agent"

    graph.add_conditional_edges(
        "update_state",
        route_after_update,
        {
            "agent": "agent",
            "finalize": "finalize",
            END: END
        }
    )

    return graph.compile()
