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

    # Prepare RTL file lists for system prompt with relative paths
    # This helps the agent distinguish between design/ and design_context/ files
    all_rtl_files = config.design_files + config.design_context_files
    rtl_file_names = [str(f.relative_to(config.design_dir)) for f in all_rtl_files]

    # Construct system prompt
    system_prompt = load_system_prompt(
        design_name=config.design_name,
        design_dir=config.design_dir,
        spec_path=config.spec_path,
        rtl_dir=config.design_dir,  # For backward compatibility
        rtl_files=rtl_file_names,
        module_header=module_header,
        design_context_enabled=config.design_context_enabled,
        testplan_enabled=config.testplan_enabled,
        max_iterations=config.max_iterations,
        sim_runs=config.sim_runs
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
        "done_reason": None
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
    _log_agent_request(state)

    # Invoke LLM (this is an API call)
    response = llm_with_tools.invoke(state["messages"])

    # Increment API call counter
    new_api_calls = state.get("api_calls", 0) + 1

    # Log agent response at DEBUG level (with updated api_calls)
    temp_state = dict(state)
    temp_state["api_calls"] = new_api_calls
    _log_agent_response(response, temp_state)

    return {
        "messages": [response],
        "api_calls": new_api_calls
    }


def _log_agent_request(state: AgentState):
    """Log the latest message being sent to the LLM at INFO level."""
    # Only log if INFO level or lower is enabled
    if not logging.root.isEnabledFor(logging.INFO):
        return

    iteration = state.get("iteration", "?")
    api_calls = state.get("api_calls", "?")
    current_coverage = state.get("current_coverage", 0.0)
    cumulative_coverage = state.get("cumulative_coverage", 0.0)
    consecutive_failures = state.get("consecutive_failures", 0)
    no_progress = state.get("no_progress_count", 0)
    messages = state.get("messages", [])

    logging.info("="*80)
    logging.info(f"API REQUEST [API Call #{api_calls} | Iter {iteration} | Cumulative: {cumulative_coverage:.1f}% | Last: {current_coverage:.1f}% | Failures: {consecutive_failures} | No Progress: {no_progress}]")
    logging.info("="*80)

    # Show only the latest message (the one being sent to LLM)
    if messages:
        latest_msg = messages[-1]
        msg_type = type(latest_msg).__name__

        logging.info(f"[MESSAGE TYPE] {msg_type}")

        # Log message content
        if hasattr(latest_msg, 'content') and latest_msg.content:
            content = latest_msg.content
            # Truncate if very long (e.g., tool results with lots of data)
            if isinstance(content, str) and len(content) > 1000:
                preview = content[:1000] + f"\n... ({len(content)} chars total)"
                logging.info(f"[CONTENT]\n{preview}\n")
            else:
                logging.info(f"[CONTENT]\n{content}\n")

        # If it's a tool message, show the tool name
        if hasattr(latest_msg, 'name') and latest_msg.name:
            logging.info(f"[TOOL NAME] {latest_msg.name}")

    logging.info("="*80 + "\n")


def _log_agent_response(response, state: AgentState):
    """Log detailed agent response at INFO level."""
    # Only log if INFO level or lower is enabled
    if not logging.root.isEnabledFor(logging.INFO):
        return

    iteration = state.get("iteration", "?")
    api_calls = state.get("api_calls", "?")
    current_coverage = state.get("current_coverage", 0.0)
    cumulative_coverage = state.get("cumulative_coverage", 0.0)
    consecutive_failures = state.get("consecutive_failures", 0)
    no_progress = state.get("no_progress_count", 0)

    logging.info("="*80)
    logging.info(f"AGENT RESPONSE [API Call #{api_calls} | Iter {iteration} | Cumulative: {cumulative_coverage:.1f}% | Last: {current_coverage:.1f}% | Failures: {consecutive_failures} | No Progress: {no_progress}]")
    logging.info("="*80)

    # Log reasoning text (if present)
    if hasattr(response, 'content') and response.content:
        logging.info(f"\n[REASONING]\n{response.content}\n")

    # Log tool calls (if present)
    if hasattr(response, 'tool_calls') and response.tool_calls:
        logging.info(f"[TOOL CALLS] {len(response.tool_calls)} tool(s) requested:")
        for i, tool_call in enumerate(response.tool_calls, 1):
            tool_name = tool_call.get('name', 'unknown')
            tool_args = tool_call.get('args', {})

            logging.info(f"\n  {i}. {tool_name}")

            # Pretty-print arguments (handle long values)
            for arg_name, arg_value in tool_args.items():
                if isinstance(arg_value, str) and len(arg_value) > 200:
                    # Truncate long string arguments (like file content)
                    preview = arg_value[:200] + f"... ({len(arg_value)} chars total)"
                    logging.info(f"     {arg_name}: {preview}")
                else:
                    logging.info(f"     {arg_name}: {arg_value}")
    else:
        logging.info("[NO TOOL CALLS] Agent did not request any tools")

    logging.info("="*80 + "\n")

def router_node(state: AgentState) -> Literal["tools", "update_state", END]:
    """
    Router node: Decide next action based on agent output.
    """
    config = state["config"]
    last_message = state["messages"][-1]

    # Check for signal_done tool call
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            if tool_call['name'] == 'signal_done':
                logging.info(f"Agent signaled done: {tool_call['args'].get('reason')}")
                return END

    # Check termination conditions
    if state["api_calls"] >= config.max_iterations:
        logging.info(f"Max iterations ({config.max_iterations}) reached - {state['api_calls']} API calls made")
        return END

    if state["consecutive_failures"] >= config.max_retries:
        logging.info("Max retries reached")
        return END

    # Route to tools if tool calls present
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"

    # Otherwise continue with agent
    return "agent"

def update_state_node(state: AgentState) -> AgentState:
    """
    Update state node: Track iterations, attempts, and coverage after tool executions.

    Priority order:
    1. Check compile failures (highest priority - stop immediately)
    2. Check simulation failures
    3. Check coverage improvement/no improvement
    """
    config = state["config"]

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
    def route_after_agent(state: AgentState) -> Literal["tools", END]:
        """Route after agent decision."""
        # Get config from state (no reload needed)
        config = state["config"]
        last_message = state["messages"][-1]

        # Check for signal_done tool call
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            for tool_call in last_message.tool_calls:
                if tool_call['name'] == 'signal_done':
                    logging.info(f"Agent signaled done: {tool_call['args'].get('reason')}")
                    return END

        # Check termination conditions
        if state["iteration"] >= config.max_iterations:
            logging.info("Max iterations reached")
            return END

        if state["consecutive_failures"] >= config.max_retries:
            logging.info("Max retries reached")
            return END

        if state["no_progress_count"] >= config.max_no_progress:
            logging.info(f"No progress after {state['no_progress_count']} attempts (MAX_NO_PROGRESS={config.max_no_progress}) - cumulative coverage stuck at {state.get('cumulative_coverage', 0.0):.1f}%")
            return END

        # Route to tools if tool calls present
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"

        # Otherwise continue with agent
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

    def route_after_update(state: AgentState) -> Literal["agent", END]:
        """Route after state update - check termination conditions with updated state."""
        # Get config from state (no reload needed)
        config = state["config"]

        # Check termination conditions with UPDATED state
        if state["iteration"] >= config.max_iterations:
            logging.info(f"Max iterations reached: {state['iteration']}/{config.max_iterations}")
            return END

        if state["consecutive_failures"] >= config.max_retries:
            logging.info(f"Max retries reached: {state['consecutive_failures']}/{config.max_retries}")
            return END

        if state["no_progress_count"] >= config.max_no_progress:
            logging.info(f"No progress after {state['no_progress_count']} attempts (MAX_NO_PROGRESS={config.max_no_progress}) - cumulative coverage stuck at {state.get('cumulative_coverage', 0.0):.1f}%")
            return END

        # Continue to agent
        return "agent"

    graph.add_conditional_edges(
        "update_state",
        route_after_update,
        {
            "agent": "agent",
            END: END
        }
    )

    return graph.compile()
