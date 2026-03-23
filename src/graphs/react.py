from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import logging
import os
from pathlib import Path

# ANSI color codes for terminal output
class Colors:
    CYAN    = '\033[96m'
    GREEN   = '\033[92m'
    YELLOW  = '\033[93m'
    MAGENTA = '\033[95m'
    RED     = '\033[91m'
    BLUE    = '\033[94m'
    BOLD    = '\033[1m'
    RESET   = '\033[0m'

from ..state.schemas import AgentState
from ..config import Config, load_config
from ..utils.design_loader import scan_design_directory, extract_module_header, extract_all_module_headers
from ..utils.tokens import count_message_tokens, format_token_count
from ..prompts.loader import load_system_prompt
from ..tools import get_all_tools, set_tool_config
import shutil


# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_phase_1_done(state: AgentState) -> bool:
    """Return True when Phase 1 (code coverage) has reached any termination condition."""
    config = state["config"]
    if state["api_calls"] >= config.max_iterations:
        return True
    if state["iteration"] > config.max_iterations:
        return True
    if state["consecutive_failures"] >= config.max_retries:
        return True
    if state["no_progress_count"] >= config.max_no_progress:
        return True
    token_count = count_message_tokens(state["messages"], config.model)
    if token_count >= config.context_window:
        return True
    return False


def _signal_done_accepted(state: AgentState) -> bool:
    """Return True if the agent's signal_done call meets termination conditions."""
    config = state["config"]
    if state.get("cumulative_coverage", 0.0) >= 100.0:
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


# ── UVM Helpers ───────────────────────────────────────────────────────────────

def _prepare_uvm_workdir(config: Config):
    """Prepare the work directory for UVM compilation.

    1. Copy the .f file to work_dir, rewriting relative paths to absolute.
    2. Replace the sequence file and test file entries so they point to
       work_dir/testbenches/ where the LLM will generate them.
    3. Create work_dir/testbenches/ and work_dir/iterations/.
    """
    work_dir = config.work_dir
    original_filelist = config.uvm_filelist

    # The .f file's relative paths are relative to the sim/ directory,
    # which is a sibling of the testbench/ directory.
    # e.g., filelist is at .../testbench/alu_core_list.f
    # paths in it are like ../testbench/X.sv and ../rtl/X.sv
    # These are relative to sim/ (one level up from testbench/, then into testbench/)
    sim_dir = config.uvm_testbench_dir.parent / "sim" if config.uvm_testbench_dir else original_filelist.parent.parent / "sim"

    # Read original .f file
    with open(original_filelist, 'r') as f:
        lines = f.readlines()

    # Rewrite paths to absolute, replacing sequence and test file entries
    new_lines = []
    seq_file = config.uvm_sequence_file  # e.g., "alu_core_seq.sv"
    test_file = f"{config.uvm_test_name}.sv"  # e.g., "alu_core_test.sv"

    testbenches_dir = work_dir / "testbenches"
    testbenches_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "iterations").mkdir(parents=True, exist_ok=True)

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("#"):
            new_lines.append(line)
            continue

        # Resolve the relative path against sim_dir
        resolved = (sim_dir / stripped).resolve()
        filename = resolved.name

        # Redirect sequence file and test file to work_dir/testbenches/
        if filename == seq_file:
            new_lines.append(str(testbenches_dir / seq_file) + "\n")
            logging.info(f"UVM .f file: redirecting {filename} → {testbenches_dir / seq_file}")
        elif filename == test_file:
            new_lines.append(str(testbenches_dir / test_file) + "\n")
            logging.info(f"UVM .f file: redirecting {filename} → {testbenches_dir / test_file}")
        else:
            new_lines.append(str(resolved) + "\n")

    # Write the modified .f file to work_dir
    work_filelist = work_dir / "filelist.f"
    with open(work_filelist, 'w') as f:
        f.writelines(new_lines)

    # Update config to use the new filelist
    config.uvm_filelist = work_filelist
    logging.info(f"UVM filelist prepared: {work_filelist}")


def _build_uvm_prompt_context(config: Config) -> dict:
    """Read UVM context files and build kwargs for load_system_prompt()."""
    # Read seq_item content
    seq_item_content = ""
    if config.uvm_seq_item_file and config.uvm_seq_item_file.exists():
        with open(config.uvm_seq_item_file, 'r') as f:
            seq_item_content = f.read()

    # Read coverage module content
    cov_module_content = ""
    if config.uvm_coverage_module_file and config.uvm_coverage_module_file.exists():
        with open(config.uvm_coverage_module_file, 'r') as f:
            cov_module_content = f.read()

    # List UVM testbench files for context
    uvm_tb_files = []
    if config.uvm_testbench_dir and config.uvm_testbench_dir.exists():
        for f in sorted(config.uvm_testbench_dir.iterdir()):
            if f.suffix == '.sv' and f.name != config.uvm_sequence_file and \
               f.name != f"{config.uvm_test_name}.sv":
                uvm_tb_files.append(str(f))

    return {
        'uvm_enabled': True,
        'uvm_seq_item_content': seq_item_content,
        'uvm_coverage_module_content': cov_module_content,
        'uvm_sequence_file': config.uvm_sequence_file,
        'uvm_test_name': config.uvm_test_name,
        'uvm_testbench_files': uvm_tb_files,
    }


# ── Graph nodes ───────────────────────────────────────────────────────────────

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
    if config.combined_coverage_enabled:
        logging.info("Combined coverage mode: starting Phase 1 (code coverage)")

    module_header = extract_all_module_headers(config.design_files)

    # ── UVM setup: prepare .f file, read context files ────────────────────
    uvm_prompt_kwargs = {}
    if config.uvm_enabled:
        _prepare_uvm_workdir(config)
        uvm_prompt_kwargs = _build_uvm_prompt_context(config)

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
        **uvm_prompt_kwargs,
    )

    config.current_iteration = 1
    config.current_attempt = 1
    set_tool_config(config)

    # coverage_phase is "code" in combined mode, None in single-mode runs
    coverage_phase = "code" if config.combined_coverage_enabled else None

    # Choose appropriate initial human message
    if config.uvm_enabled:
        human_msg = (
            "Begin UVM verification. Start by reading the specification. "
            "Then generate UVM sequences and a test file to achieve both "
            "code and functional coverage."
        )
    else:
        human_msg = "Begin verification. Start by reading the specification."

    return {
        "messages": [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_msg)
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
        "current_coverage": 0.0,
        "max_coverage": 0.0,
        "cumulative_coverage": 0.0,
        "cumulative_coverage_db": None,
        "functional_coverage_enabled": config.functional_coverage_enabled,
        "functional_coverage_target": config.functional_coverage_target,
        "functional_coverage_testbench_path": (
            str(config.functional_coverage_testbench_path)
            if config.functional_coverage_testbench_path
            else None
        ),
        "current_functional_coverage": 0.0,
        "max_functional_coverage": 0.0,
        "functional_coverage_history": [],
        "uncovered_bins": [],
        # Combined mode fields
        "coverage_phase": coverage_phase,
        "code_coverage_summary": None,
        # UVM mode
        "uvm_enabled": config.uvm_enabled,
        # Termination
        "is_done": False,
        "done_reason": None,
    }


def phase_transition_node(state: AgentState) -> AgentState:
    """
    Phase transition node: switches from code coverage (Phase 1) to
    functional coverage (Phase 2).

    Only reached when COMBINED_COVERAGE_ENABLED=1 and Phase 1 has terminated.

    Actions:
    1. Snapshot Phase 1 results into code_coverage_summary
    2. Mutate config: flip functional_coverage_enabled, update work_dir,
       set functional_coverage_testbench_path
    3. Create Phase 2 work directory structure
    4. Reset all iteration/failure counters
    5. Replace message history with fresh system prompt + human message
       so Phase 2 starts with a clean context
    6. Re-register tools with updated config
    """
    config = state["config"]

    logging.info("=" * 70)
    logging.info("PHASE TRANSITION: Code Coverage → Functional Coverage")
    logging.info(f"  Phase 1 summary:")
    logging.info(f"    Iterations:         {state['iteration']}")
    logging.info(f"    Max coverage:       {state['max_coverage']:.1f}%")
    logging.info(f"    Cumulative coverage:{state['cumulative_coverage']:.1f}%")
    logging.info("=" * 70)

    # ── 1. Snapshot Phase 1 results ────────────────────────────────────────
    code_summary = {
        "iteration":            state["iteration"],
        "max_coverage":         state["max_coverage"],
        "cumulative_coverage":  state["cumulative_coverage"],
        "cumulative_coverage_db": state.get("cumulative_coverage_db"),
        "work_dir":             state["work_dir"],
    }

    # ── 2. Mutate config for Phase 2 ───────────────────────────────────────
    # Switch work_dir: .../code_cov  →  .../func_cov
    old_work = Path(config.work_dir)
    new_work = old_work.parent / "func_cov"
    config.work_dir = new_work

    # Activate functional coverage mode
    config.functional_coverage_enabled = True

    # Resolve the functional coverage testbench path (validated at load_config time)
    funcov_tb_env = os.getenv("FUNCTIONAL_COVERAGE_TESTBENCH")
    if funcov_tb_env:
        config.functional_coverage_testbench_path = Path(funcov_tb_env)
    elif hasattr(state["config"], 'functional_coverage_testbench_path') and \
            state["config"].functional_coverage_testbench_path:
        pass  # Already set from dashboard config at load time
    # (load_config already validated existence, so no need to re-check here)

    # Reset iteration counters so Phase 2 starts fresh
    config.current_iteration = 1
    config.current_attempt = 1
    config.compile_attempts_this_iter = 0
    config.sim_attempts_this_iter = 0
    config._last_iter_for_compile = 0
    config._last_iter_for_sim = 0

    # ── 3. Create Phase 2 work directory structure ─────────────────────────
    (new_work / "testbenches").mkdir(parents=True, exist_ok=True)
    (new_work / "logs").mkdir(parents=True, exist_ok=True)
    (new_work / "coverage").mkdir(parents=True, exist_ok=True)
    logging.info(f"Phase 2 work directory created: {new_work}")

    # ── 4. Re-register tools with updated config ───────────────────────────
    set_tool_config(config)

    # ── 5. Build fresh system prompt for Phase 2 ───────────────────────────
    from ..utils.design_loader import extract_all_module_headers
    module_header = extract_all_module_headers(config.design_files)

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
    )

    phase2_human = (
        "Phase 1 (code coverage) is complete.\n"
        f"  Code coverage achieved: {state['cumulative_coverage']:.1f}%\n\n"
        "Now begin Phase 2: functional coverage.\n"
        f"A testbench template with covergroups is provided at:\n"
        f"  {config.functional_coverage_testbench_path}\n\n"
        "Read the testbench template, then generate stimulus to hit all coverage bins."
    )

    # ── Patch orphaned tool calls ───────────────────────────────────────────
    # OpenAI requires every AIMessage tool_call to be followed by a matching
    # ToolMessage. The signal_done call that triggered this transition has no
    # response yet. Inject a synthetic ToolMessage for each unanswered call
    # so the message history is valid when sent to the Phase 2 LLM.
    from langchain_core.messages import ToolMessage
    closing_tool_messages = []
    last_ai = None
    for msg in reversed(state["messages"]):
        if type(msg).__name__ == "AIMessage":
            last_ai = msg
            break
    if last_ai and hasattr(last_ai, "tool_calls") and last_ai.tool_calls:
        # Collect tool_call_ids that already have a response
        answered_ids = {
            msg.tool_call_id
            for msg in state["messages"]
            if type(msg).__name__ == "ToolMessage" and hasattr(msg, "tool_call_id")
        }
        for tc in last_ai.tool_calls:
            if tc["id"] not in answered_ids:
                closing_tool_messages.append(
                    ToolMessage(
                        content="Phase 1 complete. Transitioning to functional coverage phase.",
                        tool_call_id=tc["id"],
                        name=tc["name"],
                    )
                )

    # ── 6. Return updated state (reset messages to clean slate) ────────────
    # We do NOT use add_messages here — we return the full replacement list
    # by replacing the key directly. LangGraph merges via add_messages for
    # "messages" keys, so to truly replace we emit a brand-new list.
    # The trick: return messages as a plain replacement by using the special
    # RemoveMessage pattern isn't needed here — we just return the new list
    # and LangGraph's add_messages will append. Instead we clear first by
    # returning a state update that replaces messages entirely.
    #
    # LangGraph's add_messages reducer APPENDS. To replace the entire history
    # we must clear existing messages first. We do this by returning a list
    # that starts with the special sentinel understood by add_messages: an
    # empty list clears nothing, but wrapping in a RemoveMessage would need
    # langgraph >=0.1. The safest cross-version approach: store messages as
    # the new list. Since AgentState uses add_messages we instead return the
    # key as a *replace* by using a trick: return all existing IDs as removes
    # then add new ones.
    #
    # Simplest compatible approach: just return the two new messages.
    # The Phase 2 agent will have the Phase 1 history but the new system
    # prompt at the top will reorient it. This is the lowest-risk option.
    # If context pressure becomes an issue the caller can trim old messages.

    return {
        "messages": (
            closing_tool_messages +
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=phase2_human),
            ]
        ),
        "config":  config,
        "work_dir": str(new_work),
        "module_header": module_header,
        # Coverage phase
        "coverage_phase": "functional",
        "code_coverage_summary": code_summary,
        # Reset all counters for Phase 2
        "iteration": 1,
        "attempt": 1,
        "api_calls": 0,
        "consecutive_failures": 0,
        "no_progress_count": 0,
        # Reset code-coverage metrics (Phase 2 tracks functional coverage)
        "current_coverage": 0.0,
        "cumulative_coverage": 0.0,
        "cumulative_coverage_db": None,
        # Activate functional coverage tracking
        "functional_coverage_enabled": True,
        "functional_coverage_testbench_path": (
            str(config.functional_coverage_testbench_path)
            if config.functional_coverage_testbench_path
            else None
        ),
        "current_functional_coverage": 0.0,
        "max_functional_coverage": 0.0,
        "functional_coverage_history": [],
        "uncovered_bins": [],
        # Keep termination fields clean
        "is_done": False,
        "done_reason": None,
    }


def agent_node(state: AgentState) -> AgentState:
    """Agent node: LLM reasoning and tool selection."""
    config = state["config"]

    llm = ChatOpenAI(
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        api_key=config.openai_api_key
    )

    tools = get_all_tools()
    llm_with_tools = llm.bind_tools(tools)

    _log_agent_request(state)

    response = llm_with_tools.invoke(state["messages"])

    new_api_calls = state.get("api_calls", 0) + 1

    temp_state = dict(state)
    temp_state["api_calls"] = new_api_calls
    _log_agent_response(response, temp_state)

    return {
        "messages": [response],
        "api_calls": new_api_calls,
    }


def _log_agent_request(state: AgentState):
    """Log the latest message being sent to the LLM at INFO level."""
    if not logging.root.isEnabledFor(logging.INFO):
        return

    messages = state.get("messages", [])

    if messages:
        latest_msg = messages[-1]
        if type(latest_msg).__name__ == "AIMessage":
            return

    iteration      = state.get("iteration", "?")
    api_calls      = state.get("api_calls", "?")
    current_cov    = state.get("current_coverage", 0.0)
    cumulative_cov = state.get("cumulative_coverage", 0.0)
    cons_failures  = state.get("consecutive_failures", 0)
    no_progress    = state.get("no_progress_count", 0)
    phase          = state.get("coverage_phase")

    config = state.get("config")
    model  = config.model if config else "gpt-4"
    token_count   = count_message_tokens(messages, model)
    token_display = format_token_count(token_count, config.context_window) if config else format_token_count(token_count)

    phase_tag = f" | Phase: {phase}" if phase else ""

    logging.info(f"{Colors.CYAN}{Colors.BOLD}{'='*80}{Colors.RESET}")
    logging.info(
        f"{Colors.CYAN}{Colors.BOLD}API REQUEST "
        f"[API Call #{api_calls} | Iter {iteration}{phase_tag} | "
        f"Cumulative: {cumulative_cov:.1f}% | Last: {current_cov:.1f}% | "
        f"Failures: {cons_failures} | No Progress: {no_progress} | "
        f"Tokens: {token_display}]{Colors.RESET}"
    )
    logging.info(f"{Colors.CYAN}{'='*80}{Colors.RESET}")

    if messages:
        latest_msg = messages[-1]
        msg_type   = type(latest_msg).__name__
        logging.info(f"{Colors.CYAN}[MESSAGE TYPE] {msg_type}{Colors.RESET}")

        if hasattr(latest_msg, 'content') and latest_msg.content:
            content = latest_msg.content
            max_content_length = 500
            should_truncate = config.log_truncate if config else True

            if should_truncate and len(content) > max_content_length:
                truncated = content[:max_content_length] + f"... [truncated {len(content) - max_content_length} chars]"
                logging.info(f"{Colors.CYAN}{truncated}{Colors.RESET}")
            else:
                logging.info(f"{Colors.CYAN}{content}{Colors.RESET}")


def _log_agent_response(response, state: AgentState):
    """Log the agent's response at DEBUG level."""
    if not logging.root.isEnabledFor(logging.DEBUG):
        return

    iteration = state.get("iteration", "?")
    api_calls = state.get("api_calls", "?")

    logging.debug(f"{Colors.GREEN}{Colors.BOLD}{'='*80}{Colors.RESET}")
    logging.debug(f"{Colors.GREEN}{Colors.BOLD}AGENT RESPONSE [API Call #{api_calls} | Iter {iteration}]{Colors.RESET}")
    logging.debug(f"{Colors.GREEN}{'='*80}{Colors.RESET}")

    if hasattr(response, 'content') and response.content:
        logging.debug(f"{Colors.GREEN}[CONTENT]{Colors.RESET}")
        logging.debug(f"{Colors.GREEN}{response.content}{Colors.RESET}")

    if hasattr(response, 'tool_calls') and response.tool_calls:
        logging.debug(f"{Colors.YELLOW}[TOOL CALLS]{Colors.RESET}")
        for tool_call in response.tool_calls:
            logging.debug(f"{Colors.YELLOW}  Tool: {tool_call['name']}{Colors.RESET}")
            args_str = str(tool_call.get('args', {}))
            if len(args_str) > 200:
                args_str = args_str[:200] + "..."
            logging.debug(f"{Colors.YELLOW}  Args: {args_str}{Colors.RESET}")


def parse_tool_result(content: str) -> dict:
    """Parse tool result from string content."""
    try:
        import json
        return json.loads(content)
    except Exception:
        return {"success": False, "error": "Failed to parse tool result"}


def update_state_node(state: AgentState) -> AgentState:
    """
    Update state based on tool results.

    Checks for:
    1. compile_design failures  → increment consecutive_failures
    2. run_simulation failures  → increment consecutive_failures
    3. parse_coverage OR parse_functional_coverage success
                                → update coverage metrics, increment iteration
    """
    config = state["config"]

    # Priority 1: compile_design failures
    for msg in reversed(state["messages"][-5:]):
        if hasattr(msg, 'name') and msg.name == 'compile_design':
            result = parse_tool_result(msg.content)
            if not result.get('success', False):
                iter_num  = result.get('iteration', '?')
                retry_num = result.get('retry', '?')
                logging.warning(f"Compilation failed (iter {iter_num}, retry {retry_num})")
                return {"consecutive_failures": state["consecutive_failures"] + 1}
            break

    # Priority 2: run_simulation failures
    for msg in reversed(state["messages"][-5:]):
        if hasattr(msg, 'name') and msg.name == 'run_simulation':
            result = parse_tool_result(msg.content)
            if not result.get('success', False):
                iter_num  = result.get('iteration', '?')
                retry_num = result.get('retry', '?')
                logging.warning(f"Simulation failed (iter {iter_num}, retry {retry_num})")
                return {"consecutive_failures": state["consecutive_failures"] + 1}
            break

    # Priority 3: coverage parse results (latest message only)
    latest_msg = state["messages"][-1] if state["messages"] else None

    # Validate correct tool for current mode
    # In UVM mode, both parse_coverage and parse_functional_coverage are valid
    # since UVM targets both code and functional coverage simultaneously.
    uvm_mode = getattr(config, 'uvm_enabled', False)
    if not uvm_mode and latest_msg and hasattr(latest_msg, 'name'):
        tool_name = latest_msg.name

        if config.functional_coverage_enabled and tool_name == 'parse_coverage':
            logging.error(f"{Colors.RED}❌ WRONG TOOL: Agent called parse_coverage in FUNCTIONAL coverage mode!{Colors.RESET}")
            logging.error(f"{Colors.RED}   Should have called: parse_functional_coverage{Colors.RESET}")
            return {}

        if not config.functional_coverage_enabled and tool_name == 'parse_functional_coverage':
            logging.error(f"{Colors.RED}❌ WRONG TOOL: Agent called parse_functional_coverage in CODE coverage mode!{Colors.RESET}")
            logging.error(f"{Colors.RED}   Should have called: parse_coverage{Colors.RESET}")
            return {}

    if latest_msg and hasattr(latest_msg, 'name') and \
            latest_msg.name in ['parse_coverage', 'parse_functional_coverage']:
        result = parse_tool_result(latest_msg.content)

        if result.get('success'):
            iteration_coverage = result.get('iteration_coverage', result.get('total_coverage', 0.0))
            cumulative_coverage = result.get('cumulative_coverage', result.get('total_coverage', 0.0))
            cumulative_db       = result.get('cumulative_coverage_db')
            next_iteration      = state["iteration"] + 1

            config.current_iteration = next_iteration
            prev_cumulative = state.get("cumulative_coverage", 0.0)

            if cumulative_coverage > prev_cumulative:
                logging.info(
                    f"Cumulative coverage improved: {prev_cumulative:.1f}% → "
                    f"{cumulative_coverage:.1f}% (this iteration: {iteration_coverage:.1f}%)"
                )
                return {
                    "current_coverage":     iteration_coverage,
                    "max_coverage":         max(state["max_coverage"], iteration_coverage),
                    "cumulative_coverage":  cumulative_coverage,
                    "cumulative_coverage_db": cumulative_db,
                    "iteration":            next_iteration,
                    "consecutive_failures": 0,
                    "no_progress_count":    0,
                }
            else:
                logging.warning(
                    f"No cumulative coverage improvement: {cumulative_coverage:.1f}% "
                    f"(this iteration: {iteration_coverage:.1f}%)"
                )
                return {
                    "current_coverage":     iteration_coverage,
                    "cumulative_coverage":  cumulative_coverage,
                    "cumulative_coverage_db": cumulative_db,
                    "iteration":            next_iteration,
                    "consecutive_failures": 0,
                    "no_progress_count":    state["no_progress_count"] + 1,
                }

    return {}


# ── Graph wiring ───────────────────────────────────────────────────────────────

def create_react_graph() -> StateGraph:
    """Create the ReAct agent graph."""

    graph = StateGraph(AgentState)

    # ── Nodes ──────────────────────────────────────────────────────────────
    graph.add_node("initialize",        initialize_node)
    graph.add_node("agent",             agent_node)
    graph.add_node("tools",             ToolNode(get_all_tools()))
    graph.add_node("update_state",      update_state_node)
    graph.add_node("phase_transition",  phase_transition_node)

    # ── Static edges ───────────────────────────────────────────────────────
    graph.set_entry_point("initialize")
    graph.add_edge("initialize",       "agent")
    graph.add_edge("tools",            "update_state")
    graph.add_edge("phase_transition", "agent")   # Phase 2 starts fresh agent loop

    # ── Routing helper ─────────────────────────────────────────────────────
    def _termination_route(state: AgentState) -> str:
        """
        Shared termination check used by both route_after_agent and
        route_after_update.

        Returns:
            "phase_transition" – Phase 1 done, combined mode → go to Phase 2
            END                – truly done (single mode, or Phase 2 finished)
            None               – not done yet
        """
        config = state["config"]

        terminated = (
            state["api_calls"]          >= config.max_iterations or
            state["iteration"]          >  config.max_iterations or
            state["consecutive_failures"] >= config.max_retries  or
            state["no_progress_count"]  >= config.max_no_progress or
            count_message_tokens(state["messages"], config.model) >= config.context_window
        )

        if not terminated:
            return None   # Keep running

        # We are terminating — decide where to go
        if (config.combined_coverage_enabled and
                state.get("coverage_phase") == "code"):
            # Phase 1 is done → transition to Phase 2
            logging.info("Phase 1 termination condition met → transitioning to Phase 2")
            return "phase_transition"

        # Single-mode run, or Phase 2 ending → truly done
        return END

    # ── Conditional routing from agent ─────────────────────────────────────
    def route_after_agent(state: AgentState) -> Literal["tools", "agent", "phase_transition", "__end__"]:
        config      = state["config"]
        last_message = state["messages"][-1]

        # ── Handle signal_done tool call ────────────────────────────────────
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            for tool_call in last_message.tool_calls:
                if tool_call['name'] == 'signal_done':
                    reason = tool_call['args'].get('reason', 'unknown')
                    logging.info(f"Agent called signal_done with reason: {reason}")

                    # Check 100% coverage specifically
                    if reason == "coverage_complete":
                        cumulative_cov = state.get("cumulative_coverage", 0.0)
                        if cumulative_cov >= 100.0:
                            logging.info("✓ Accepting signal_done: 100% coverage achieved!")
                            # In combined mode Phase 1 → go to Phase 2
                            if (config.combined_coverage_enabled and
                                    state.get("coverage_phase") == "code"):
                                logging.info("Combined mode: transitioning to Phase 2")
                                return "phase_transition"
                            return END
                        else:
                            logging.warning(
                                f"⚠️  Agent claimed coverage_complete but coverage is "
                                f"{cumulative_cov:.1f}%"
                            )

                    # Other accepted termination reasons
                    if _signal_done_accepted(state):
                        logging.info(f"✓ Accepting signal_done: {reason}")
                        if (config.combined_coverage_enabled and
                                state.get("coverage_phase") == "code"):
                            logging.info("Combined mode: transitioning to Phase 2")
                            return "phase_transition"
                        return END
                    else:
                        logging.warning(
                            f"⚠️  REJECTING signal_done: termination conditions not met\n"
                            f"   consecutive_failures: {state['consecutive_failures']}/{config.max_retries}\n"
                            f"   no_progress_count:    {state['no_progress_count']}/{config.max_no_progress}\n"
                            f"   api_calls:            {state['api_calls']}/{config.max_iterations}\n"
                            f"   iteration:            {state['iteration']}/{config.max_iterations}\n"
                            f"   cumulative_coverage:  {state.get('cumulative_coverage', 0.0):.1f}%"
                        )
                        break  # Fall through to normal tool processing

        # ── Check hard termination conditions ──────────────────────────────
        route = _termination_route(state)
        if route is not None:
            return route

        # ── Route to tools if tool calls present ───────────────────────────
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"

        return "agent"

    graph.add_conditional_edges(
        "agent",
        route_after_agent,
        {
            "tools":            "tools",
            "agent":            "agent",
            "phase_transition": "phase_transition",
            END:                END,
        }
    )

    # ── Conditional routing after state update ─────────────────────────────
    def route_after_update(state: AgentState) -> Literal["agent", "phase_transition", "__end__"]:
        route = _termination_route(state)
        if route is not None:
            return route
        return "agent"

    graph.add_conditional_edges(
        "update_state",
        route_after_update,
        {
            "agent":            "agent",
            "phase_transition": "phase_transition",
            END:                END,
        }
    )

    return graph.compile()
