from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, RemoveMessage
import logging
import json as _json
import os
import shutil
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
from ..prompts.loader import load_system_prompt
from ..tools import get_all_tools, set_tool_config
from ..tools.analysis import get_cumulative_coverage_db, _create_annotated_source


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


def _get_functional_coverage(state: AgentState) -> float:
    """Get the current functional coverage from state or cumulative report.

    The LLM may not always call parse_functional_coverage explicitly,
    so we also check the cumulative report file on disk as a fallback.
    """
    # First check state (set when LLM calls parse_functional_coverage)
    funcov = state.get("current_functional_coverage", 0.0)
    if funcov > 0.0:
        return funcov

    # Fallback: read the cumulative functional coverage report from disk
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
    """Return True if the agent's signal_done call meets termination conditions."""
    config = state["config"]
    if state.get("cumulative_coverage", 0.0) >= 100.0:
        return True
    # In UVM functional mode, functional coverage reaching target is a valid completion
    # (code coverage is often dragged down by UVM infrastructure lines).
    # In UVM line mode, only cumulative_coverage >= 100% matters (already checked above).
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


# ── UVM Helpers ───────────────────────────────────────────────────────────────

def _prepare_uvm_workdir(config: Config):
    """Prepare the work directory for UVM compilation.

    1. Copy the .f file to work_dir, rewriting relative paths to absolute.
    2. Replace the sequence file, test file, and driver file entries so they
       point to work_dir/testbenches/ where the LLM will generate/modify them.
    3. Auto-detect the driver file and copy original to work_dir/testbenches/.
    4. Create work_dir/testbenches/ and work_dir/iterations/.
    """
    import re as _re

    work_dir = config.work_dir
    original_filelist = config.uvm_filelist

    # The .f file's relative paths are relative to the sim/ directory,
    # which is a sibling of the testbench/ directory.
    sim_dir = config.uvm_testbench_dir.parent / "sim" if config.uvm_testbench_dir else original_filelist.parent.parent / "sim"

    # Auto-detect the driver file from the testbench directory
    driver_file = None
    if config.uvm_testbench_dir and config.uvm_testbench_dir.exists():
        for f in config.uvm_testbench_dir.iterdir():
            if f.suffix == '.sv':
                try:
                    content = f.read_text()
                    if _re.search(r'extends\s+uvm_driver', content):
                        driver_file = f
                        logging.info(f"UVM driver auto-detected: {f.name}")
                        break
                except Exception:
                    pass

    if driver_file:
        config.uvm_driver_file = driver_file
    else:
        logging.warning("Could not auto-detect UVM driver file")

    # Read original .f file
    with open(original_filelist, 'r') as f:
        lines = f.readlines()

    # Rewrite paths to absolute, replacing sequence, test, and driver entries
    new_lines = []
    seq_file = config.uvm_sequence_file  # e.g., "alu_core_seq.sv"
    test_file = f"{config.uvm_test_name}.sv"  # e.g., "alu_core_test.sv"
    driver_filename = driver_file.name if driver_file else None

    testbenches_dir = work_dir / "testbenches"
    testbenches_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "iterations").mkdir(parents=True, exist_ok=True)

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("#"):
            new_lines.append(line)
            continue

        # Skip compiler directives and env-var lines — these are handled
        # separately by the UVM compilation step (vlog already gets
        # +incdir+$UVM_HOME/src and uvm_pkg.sv via explicit flags).
        if stripped.startswith("+") or "$" in stripped:
            logging.info(f"UVM .f file: skipping compiler directive: {stripped}")
            continue

        # Resolve the relative path against sim_dir
        resolved = (sim_dir / stripped).resolve()
        filename = resolved.name

        # Redirect sequence file, test file, and driver to work_dir/testbenches/
        if filename == seq_file:
            new_lines.append(str(testbenches_dir / seq_file) + "\n")
            logging.info(f"UVM .f file: redirecting {filename} → {testbenches_dir / seq_file}")
        elif filename == test_file:
            new_lines.append(str(testbenches_dir / test_file) + "\n")
            logging.info(f"UVM .f file: redirecting {filename} → {testbenches_dir / test_file}")
        elif driver_filename and filename == driver_filename:
            # Redirect driver to work_dir/testbenches/ for infra modification
            dest = testbenches_dir / driver_filename
            new_lines.append(str(dest) + "\n")
            logging.info(f"UVM .f file: redirecting driver {filename} → {dest}")
        else:
            new_lines.append(str(resolved) + "\n")

    # Copy original driver to work_dir/testbenches/ (unmodified starting point)
    if driver_file:
        dest_driver = testbenches_dir / driver_file.name
        shutil.copy2(driver_file, dest_driver)
        logging.info(f"UVM driver copied to work_dir: {dest_driver}")

    # Write the modified .f file to work_dir
    work_filelist = work_dir / "filelist.f"
    with open(work_filelist, 'w') as f:
        f.writelines(new_lines)

    # Update config to use the new filelist
    config.uvm_filelist = work_filelist
    logging.info(f"UVM filelist prepared: {work_filelist}")


def _build_uvm_prompt_context(config: Config) -> dict:
    """Read UVM context files and build kwargs for load_system_prompt()."""
    import re as _re

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

    # List UVM testbench files for context and extract interface/env names
    uvm_tb_files = []
    uvm_interface_name = None
    uvm_env_class = None
    if config.uvm_testbench_dir and config.uvm_testbench_dir.exists():
        for f in sorted(config.uvm_testbench_dir.iterdir()):
            if f.suffix == '.sv' and f.name != config.uvm_sequence_file and \
               f.name != f"{config.uvm_test_name}.sv":
                uvm_tb_files.append(str(f))
                # Extract interface and env class names from file contents
                try:
                    content = f.read_text()
                    if not uvm_interface_name:
                        # Match top-level interface declaration (start of line)
                        m = _re.search(r'^interface\s+(\w+)', content, _re.MULTILINE)
                        if m:
                            uvm_interface_name = m.group(1)
                    if not uvm_env_class:
                        m = _re.search(r'class\s+(\w+)\s+extends\s+uvm_env', content)
                        if m:
                            uvm_env_class = m.group(1)
                except Exception:
                    pass

    if uvm_interface_name:
        logging.info(f"UVM interface name detected: {uvm_interface_name}")
    if uvm_env_class:
        logging.info(f"UVM env class detected: {uvm_env_class}")

    return {
        'uvm_enabled': True,
        'uvm_seq_item_content': seq_item_content,
        'uvm_coverage_module_content': cov_module_content,
        'uvm_sequence_file': config.uvm_sequence_file,
        'uvm_test_name': config.uvm_test_name,
        'uvm_testbench_files': uvm_tb_files,
        'uvm_interface_name': uvm_interface_name,
        'uvm_env_class': uvm_env_class,
        'uvm_coverage_mode': config.uvm_coverage_mode,
    }


def _should_generate_hole_report(state: AgentState) -> bool:
    # Current phase coverage below 100%
    if state.get("cumulative_coverage", 0.0) < 100.0:
        return True
    # In combined mode, check if Phase 1 code coverage was below 100%
    config = state.get("config")
    if config and getattr(config, "combined_coverage_enabled", False):
        code_summary = state.get("code_coverage_summary") or {}
        if code_summary.get("cumulative_coverage", 0.0) < 100.0:
            return True
    return False


def _maybe_generate_hole_report(state: AgentState) -> None:
    """
    Generate a coverage hole report if at least one stage is below 100%.

    Delegates to ``generate_coverage_hole_report`` in
    ``src.utils.questasim``.  All errors are caught and logged so that a
    report-generation failure never prevents the agent from terminating
    cleanly.
    """
    try:
        from ..utils.questasim import generate_coverage_hole_report
        config      = state["config"]
        report_path = generate_coverage_hole_report(state, config.simulator_path)
        if report_path:
            logging.info(
                f"{Colors.GREEN}Coverage hole report generated: {report_path}{Colors.RESET}"
            )
        else:
            logging.warning("Coverage hole report generation returned None – check logs")
    except Exception as e:
        logging.error(f"_maybe_generate_hole_report failed: {e}")


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
        # Store detected names on config for use by validators
        if uvm_prompt_kwargs.get('uvm_interface_name'):
            config.uvm_interface_name = uvm_prompt_kwargs['uvm_interface_name']
        if uvm_prompt_kwargs.get('uvm_env_class'):
            config.uvm_env_class = uvm_prompt_kwargs['uvm_env_class']

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

    # coverage_phase is "code" in combined mode, None in single-mode runs
    coverage_phase = "code" if config.combined_coverage_enabled else None

    # Choose appropriate initial human message
    if config.uvm_enabled:
        if config.uvm_coverage_mode == "line":
            human_msg = (
                "Begin UVM verification. Start by reading the specification. "
                "Then generate UVM sequences and a test file to achieve "
                "maximum line/statement coverage of the RTL design."
            )
        else:
            human_msg = (
                "Begin UVM verification. Start by reading the specification. "
                "Then generate UVM sequences and a test file to achieve both "
                "code and functional coverage."
            )
    else:
        human_msg = "Begin verification. Start by reading the specification."

    emit("human_message", {
        "source": "init",
        "content": human_msg,
    })

    # Initialize state
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
        "no_tool_call_count": 0,
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
        "uvm_coverage_mode": config.uvm_coverage_mode,
        # Infrastructure modification pipeline
        "infra_modification_enabled": False,
        "original_driver_path": (
            str(config.uvm_driver_file) if getattr(config, 'uvm_driver_file', None) else None
        ),
        # Termination
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
    from langchain_core.messages import ToolMessage
    closing_tool_messages = []
    last_ai = None
    for msg in reversed(state["messages"]):
        if type(msg).__name__ == "AIMessage":
            last_ai = msg
            break
    if last_ai and hasattr(last_ai, "tool_calls") and last_ai.tool_calls:
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
        "no_tool_call_count": 0,
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
    global _cumulative_tokens

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

    tools = get_all_tools()
    llm_with_tools = llm.bind_tools(tools)

    # Get messages and apply nudge if text-only responses detected
    messages = state.get("messages", [])
    no_tool_count = state.get("no_tool_call_count", 0)
    infra_mod_enabled = state.get("infra_modification_enabled", False)

    if no_tool_count >= 1:
        infra_hint = ""
        if infra_mod_enabled:
            infra_hint = " or modify the driver"
        elif (getattr(config, 'uvm_enabled', False) and
              getattr(config, 'uvm_driver_file', None)):
            infra_hint = (
                "\n5. Call request_infra_modification if you believe the driver "
                "protocol is blocking coverage bins (e.g., timing, back-to-back "
                "transactions). This will grant you permission to modify the driver."
            )

        nudge = HumanMessage(content=(
            "You responded with text only — no tool calls. "
            "You MUST take action now. Either:\n"
            "1. Call plan_coverage_strategy to analyze uncovered bins and plan your approach\n"
            "2. Call write_file to generate new sequence/test files"
            + (" or modify the driver" if infra_mod_enabled else "") + "\n"
            "3. Call compile_design to compile\n"
            "4. Call signal_done if you believe no further progress is possible"
            + infra_hint + "\n"
            "Do NOT respond with only text — you must call a tool."
        ))
        messages = list(messages) + [nudge]

    # Increment API call counter before logging so REQUEST and RESPONSE show the same number
    new_api_calls = state.get("api_calls", 0) + 1
    request_state = dict(state)
    request_state["api_calls"] = new_api_calls

    # Log what we're sending to the LLM (before API call)
    log_agent_request(request_state)

    # --- JSONL: api_request event ---
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

    try:
        response = llm_with_tools.invoke(messages)
    except Exception as e:
        import traceback
        logging.error(f"{Colors.RED}{'='*80}{Colors.RESET}")
        logging.error(f"{Colors.RED}LLM API CALL FAILED{Colors.RESET}")
        logging.error(f"{Colors.RED}Error: {e}{Colors.RESET}")
        logging.error(f"{Colors.RED}Traceback:\n{traceback.format_exc()}{Colors.RESET}")
        logging.error(f"{Colors.RED}{'='*80}{Colors.RESET}")
        # Re-raise so LangGraph terminates the run
        raise

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

    result = {
        "messages": [response],
        "api_calls": new_api_calls,
        "no_tool_call_count": no_tool_call_count,
        "token_usage": [token_record]
    }

    return result


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
    Update state based on tool results.

    Priority order:
    0a. Check run_verification_cycle results (composite tool)
    0b. Check request_infra_modification (UVM infra mod grant)
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

    # Priority 0a: Check for run_verification_cycle results (composite tool)
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
            # Full success — mirror parse_coverage success logic
            coverage_result = result.get("coverage_result", {})
            iteration_coverage = coverage_result.get(
                "iteration_coverage", coverage_result.get("total_coverage", 0.0)
            )
            cumulative_coverage = coverage_result.get(
                "cumulative_coverage", coverage_result.get("total_coverage", 0.0)
            )
            cumulative_db = coverage_result.get("cumulative_coverage_db")
            next_iteration = state["iteration"] + 1

            config.current_iteration = next_iteration
            prev_cumulative = state.get("cumulative_coverage", 0.0)

            if cumulative_coverage > prev_cumulative:
                logging.info(
                    f"Cumulative coverage improved: {prev_cumulative:.2f}% → "
                    f"{cumulative_coverage:.2f}% (this iteration: {iteration_coverage:.2f}%)"
                )
                return _emit_and_return("verification_cycle_coverage_improved", {
                    "current_coverage": iteration_coverage,
                    "max_coverage": max(state["max_coverage"], iteration_coverage),
                    "cumulative_coverage": cumulative_coverage,
                    "cumulative_coverage_db": cumulative_db,
                    "iteration": next_iteration,
                    "consecutive_failures": 0,
                    "no_progress_count": 0,
                })
            else:
                logging.warning(
                    f"No cumulative coverage improvement: {cumulative_coverage:.2f}% "
                    f"(this iteration: {iteration_coverage:.2f}%)"
                )
                return _emit_and_return("verification_cycle_no_improvement", {
                    "current_coverage": iteration_coverage,
                    "cumulative_coverage": cumulative_coverage,
                    "cumulative_coverage_db": cumulative_db,
                    "iteration": next_iteration,
                    "consecutive_failures": 0,
                    "no_progress_count": state["no_progress_count"] + 1,
                })

    # Priority 0b: request_infra_modification → enable infra mod in state
    for msg in reversed(state["messages"][-5:]):
        if hasattr(msg, 'name') and msg.name == 'request_infra_modification':
            result = parse_tool_result(msg.content)
            if result.get('infra_modification_granted'):
                if not state.get("infra_modification_enabled", False):
                    logging.info(
                        f"{Colors.MAGENTA}{'='*80}{Colors.RESET}\n"
                        f"{Colors.MAGENTA}INFRASTRUCTURE MODIFICATION GRANTED (LLM-requested){Colors.RESET}\n"
                        f"{Colors.MAGENTA}{'='*80}{Colors.RESET}"
                    )
                return {"infra_modification_enabled": True}
            break

    # Priority 1: Check for compile_design failures
    for msg in reversed(state["messages"][-5:]):
        if hasattr(msg, 'name') and msg.name == 'compile_design':
            result = parse_tool_result(msg.content)
            if not result.get('success', False):
                iter_num  = result.get('iteration', '?')
                retry_num = result.get('retry', '?')
                logging.warning(f"Compilation failed (iter {iter_num}, retry {retry_num})")
                return _emit_and_return("compile_fail", {
                    "consecutive_failures": state["consecutive_failures"] + 1
                })
            break  # Found compile result, move to next check

    # Priority 2: run_simulation failures
    for msg in reversed(state["messages"][-5:]):
        if hasattr(msg, 'name') and msg.name == 'run_simulation':
            result = parse_tool_result(msg.content)
            if not result.get('success', False):
                iter_num  = result.get('iteration', '?')
                retry_num = result.get('retry', '?')
                logging.warning(f"Simulation failed (iter {iter_num}, retry {retry_num})")
                return _emit_and_return("sim_fail", {
                    "consecutive_failures": state["consecutive_failures"] + 1
                })
            break  # Found sim result, move to next check

    # Priority 3: coverage parse results (latest message only)
    latest_msg = state["messages"][-1] if state["messages"] else None

    # Validate correct tool for current mode
    uvm_mode = getattr(config, 'uvm_enabled', False)
    uvm_cov_mode = getattr(config, 'uvm_coverage_mode', 'functional')

    if latest_msg and hasattr(latest_msg, 'name'):
        tool_name = latest_msg.name

        if uvm_mode and uvm_cov_mode == "line":
            # UVM line coverage mode: only parse_coverage is valid
            if tool_name == 'parse_functional_coverage':
                logging.error(f"{Colors.RED}❌ WRONG TOOL: Agent called parse_functional_coverage in UVM LINE coverage mode!{Colors.RESET}")
                logging.error(f"{Colors.RED}   Should have called: parse_coverage{Colors.RESET}")
                return {}
        elif not uvm_mode:
            # Non-UVM mode: existing validation
            if config.functional_coverage_enabled and tool_name == 'parse_coverage':
                logging.error(f"{Colors.RED}❌ WRONG TOOL: Agent called parse_coverage in FUNCTIONAL coverage mode!{Colors.RESET}")
                logging.error(f"{Colors.RED}   Should have called: parse_functional_coverage{Colors.RESET}")
                return {}

            if not config.functional_coverage_enabled and tool_name == 'parse_functional_coverage':
                logging.error(f"{Colors.RED}❌ WRONG TOOL: Agent called parse_functional_coverage in CODE coverage mode!{Colors.RESET}")
                logging.error(f"{Colors.RED}   Should have called: parse_coverage{Colors.RESET}")
                return {}
        # else: uvm_mode + functional => both parse_coverage and parse_functional_coverage are valid

    if latest_msg and hasattr(latest_msg, 'name') and \
            latest_msg.name in ['parse_coverage', 'parse_functional_coverage']:
        result = parse_tool_result(latest_msg.content)
        is_funcov = latest_msg.name == 'parse_functional_coverage'

        if result.get('success'):
            iteration_coverage  = result.get('iteration_coverage', result.get('total_coverage', 0.0))
            cumulative_coverage = result.get('cumulative_coverage', result.get('total_coverage', 0.0))
            cumulative_db       = result.get('cumulative_coverage_db')
            next_iteration      = state["iteration"] + 1

            config.current_iteration = next_iteration
            prev_cumulative = state.get("cumulative_coverage", 0.0)

            # Track functional coverage separately so code coverage
            # results don't overwrite it (and vice versa)
            updates = {}
            if is_funcov:
                updates["current_functional_coverage"] = cumulative_coverage
                updates["max_functional_coverage"] = max(
                    state.get("max_functional_coverage", 0.0), cumulative_coverage
                )

            if cumulative_coverage > prev_cumulative:
                logging.info(
                    f"Cumulative coverage improved: {prev_cumulative:.2f}% → "
                    f"{cumulative_coverage:.2f}% (this iteration: {iteration_coverage:.2f}%)"
                )
                return _emit_and_return("coverage_improved", {
                    "current_coverage": iteration_coverage,
                    "max_coverage": max(state["max_coverage"], iteration_coverage),
                    "cumulative_coverage": cumulative_coverage,
                    "cumulative_coverage_db": cumulative_db,
                    "iteration": next_iteration,
                    "consecutive_failures": 0,
                    "no_progress_count": 0,
                    **updates,
                })
            else:
                logging.warning(
                    f"No cumulative coverage improvement: {cumulative_coverage:.2f}% "
                    f"(this iteration: {iteration_coverage:.2f}%)"
                )
                return _emit_and_return("no_improvement", {
                    "current_coverage": iteration_coverage,
                    "cumulative_coverage": cumulative_coverage,
                    "cumulative_coverage_db": cumulative_db,
                    "iteration": next_iteration,
                    "consecutive_failures": 0,
                    "no_progress_count": state["no_progress_count"] + 1,
                    **updates,
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

    if cumulative_coverage >= 100.0:
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

    # Parse latest cumulative coverage for the report
    missed_coverage_info = ""
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

    finalize_message = (
        f"FRAMEWORK NOTICE: Verification terminated (reason: {reason}). "
        f"Final cumulative coverage: {cumulative_coverage:.2f}%. "
        f"Iterations completed: {iteration - 1}.\n\n"
        f"You MUST now write your final run report to `report.md` using `write_file`. "
        f"This is your LAST turn — only `write_file` tool calls will be executed. "
        f"Do NOT call `parse_coverage`, `read_file`, or any other tool. "
        f"If you need additional context you haven't already gathered, note it under "
        f"'Next Steps' in your report.\n\n"
        f"The report MUST classify ALL remaining uncovered lines by category "
        f"(unreachable, excludable, potential bugs, needs more effort). "
        f"Follow the report requirements from your instructions (Step 7)."
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

        # Check each condition individually so we can log the reason
        reason = None
        if state["api_calls"] >= config.max_iterations:
            reason = f"max API calls reached ({state['api_calls']}/{config.max_iterations})"
        elif state["iteration"] > config.max_iterations:
            reason = f"max iterations reached ({state['iteration']}/{config.max_iterations})"
        elif state["consecutive_failures"] >= config.max_retries:
            reason = f"max consecutive failures ({state['consecutive_failures']}/{config.max_retries})"
        elif state["no_progress_count"] >= config.max_no_progress:
            reason = f"max no-progress count ({state['no_progress_count']}/{config.max_no_progress})"
        else:
            token_count = count_message_tokens(state["messages"], config.model)
            if token_count >= config.context_window:
                reason = f"context window exceeded ({token_count}/{config.context_window} tokens)"

        if reason is None:
            return None   # Keep running

        # We are terminating — log and decide where to go
        cumulative_cov = state.get("cumulative_coverage", 0.0)
        funcov = _get_functional_coverage(state)
        logging.info(
            f"{Colors.RED}{Colors.BOLD}{'='*80}{Colors.RESET}\n"
            f"{Colors.RED}{Colors.BOLD}TERMINATING: {reason}{Colors.RESET}\n"
            f"{Colors.RED}  Code coverage:       {cumulative_cov:.1f}%{Colors.RESET}\n"
            f"{Colors.RED}  Functional coverage: {funcov:.1f}%{Colors.RESET}\n"
            f"{Colors.RED}  Iterations:          {state.get('iteration', 0)}{Colors.RESET}\n"
            f"{Colors.RED}  API calls:           {state.get('api_calls', 0)}{Colors.RESET}\n"
            f"{Colors.RED}{Colors.BOLD}{'='*80}{Colors.RESET}"
        )

        if (config.combined_coverage_enabled and
                state.get("coverage_phase") == "code"):
            logging.info("Phase 1 termination condition met → transitioning to Phase 2")
            return "phase_transition"

        # Single-mode run, or Phase 2 ending → truly done
        return END

    # ── Conditional routing from agent ─────────────────────────────────────
    def route_after_agent(state: AgentState) -> Literal["tools", "agent", "finalize", "phase_transition", END]:
        config      = state["config"]
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
            return _route(END, "finalize: no write_file call, ending")

        # ── Handle signal_done tool call ────────────────────────────────────
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            for tool_call in last_message.tool_calls:
                if tool_call['name'] == 'signal_done':
                    reason = tool_call['args'].get('reason', 'unknown')
                    logging.info(f"Agent called signal_done with reason: {reason}")

                    # Check 100% coverage specifically
                    if reason == "coverage_complete":
                        cumulative_cov = state.get("cumulative_coverage", 0.0)
                        funcov = _get_functional_coverage(state)
                        funcov_target = getattr(config, 'functional_coverage_target', 100.0)
                        uvm_mode = getattr(config, 'uvm_enabled', False)
                        uvm_cov_mode = getattr(config, 'uvm_coverage_mode', 'functional')
                        # Accept if code coverage is 100%, OR in UVM functional mode if
                        # functional coverage meets target (code coverage is
                        # often dragged down by UVM infrastructure lines).
                        # In UVM line mode, only cumulative code coverage matters.
                        if cumulative_cov >= 100.0 or (uvm_mode and uvm_cov_mode == "functional" and funcov >= funcov_target):
                            logging.info(
                                f"✓ Accepting signal_done: coverage target met! "
                                f"(code={cumulative_cov:.1f}%, funcov={funcov:.1f}%)"
                            )
                            # In combined mode Phase 1 → go to Phase 2
                            if (config.combined_coverage_enabled and
                                    state.get("coverage_phase") == "code"):
                                logging.info("Combined mode: transitioning to Phase 2")
                                return "phase_transition"
                            # 100% on final phase – route to finalize for report
                            return _route("finalize", "signal_done: coverage_complete")
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
                        # Generate hole report before routing to finalize
                        if _should_generate_hole_report(state):
                            _maybe_generate_hole_report(state)
                        return _route("finalize", f"signal_done: {reason}")
                    else:
                        # Increment no_progress_count on rejection so repeated
                        # signal_done calls eventually trigger termination.
                        # Without this, the LLM enters a deadlock: it knows it
                        # can't improve coverage but the counter never reaches
                        # max_no_progress because no simulations are running.
                        state["no_progress_count"] = state.get("no_progress_count", 0) + 1
                        logging.warning(
                            f"⚠️  REJECTING signal_done: termination conditions not met\n"
                            f"   consecutive_failures: {state['consecutive_failures']}/{config.max_retries}\n"
                            f"   no_progress_count:    {state['no_progress_count']}/{config.max_no_progress}\n"
                            f"   api_calls:            {state['api_calls']}/{config.max_iterations}\n"
                            f"   iteration:            {state['iteration']}/{config.max_iterations}\n"
                            f"   cumulative_coverage:  {state.get('cumulative_coverage', 0.0):.1f}%"
                        )
                        break  # Fall through to normal tool processing

        # ── Check hard termination conditions — route to finalize for report ─
        route = _termination_route(state)
        if route is not None:
            if route == END:
                # Generate hole report before handing off to finalize
                if _should_generate_hole_report(state):
                    _maybe_generate_hole_report(state)
                return _route("finalize", "hard_termination")
            return route  # "phase_transition"

        # ── Route to tools if tool calls present ───────────────────────────
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            tool_names = [tc.get('name', '?') for tc in last_message.tool_calls]
            return _route("tools", f"tool_calls: {tool_names}")

        # ── No tool calls — LLM responded with text only ─────────────────
        # Counter is already updated by agent_node via state return dict.
        # Nudge is injected immediately (no_tool_count >= 1) in agent_node.
        no_tool_count = state.get("no_tool_call_count", 0)

        if no_tool_count >= config.max_no_tool_calls:
            logging.info(f"Agent returned {no_tool_count} consecutive responses with no tool calls — routing to finalize")
            return _route("finalize", f"max_no_tool_calls ({no_tool_count}/{config.max_no_tool_calls})")

        logging.warning(
            f"{Colors.YELLOW}⚠️  LLM responded with text only (no tool calls), "
            f"count: {no_tool_count} — nudge will be injected.{Colors.RESET}"
        )
        return _route("agent", "no_tool_calls, retrying")

    graph.add_conditional_edges(
        "agent",
        route_after_agent,
        {
            "tools":            "tools",
            "agent":            "agent",
            "finalize":         "finalize",
            "phase_transition": "phase_transition",
            END:                END,
        }
    )

    # After tools, update state, prune old messages, then check termination
    graph.add_edge("tools", "update_state")
    graph.add_node("prune_context", prune_verification_cycles)
    graph.add_edge("update_state", "prune_context")

    # Finalize node: injects message for agent to write report, then routes to agent
    graph.add_node("finalize", finalize_node)
    graph.add_edge("finalize", "agent")

    def route_after_update(state: AgentState) -> Literal["agent", "finalize", "phase_transition", END]:
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

        # Coverage complete: check if phase transition needed, else route to finalize
        cumulative = state.get("cumulative_coverage", 0.0)
        if cumulative >= 100.0:
            if (config.combined_coverage_enabled and
                    state.get("coverage_phase") == "code"):
                logging.info(f"Coverage complete ({cumulative:.2f}%) — transitioning to Phase 2")
                return _route("phase_transition", f"coverage_complete ({cumulative:.2f}%)")
            logging.info(f"Coverage complete ({cumulative:.2f}%) — routing to finalize")
            return _route("finalize", f"coverage_complete ({cumulative:.2f}%)")

        # Helper: termination check that routes to phase_transition (combined mode) or finalize
        def _term(cond, reason_str):
            if not cond:
                return None
            if (config.combined_coverage_enabled and
                    state.get("coverage_phase") == "code"):
                logging.info(f"{reason_str} — transitioning to Phase 2")
                return _route("phase_transition", reason_str)
            logging.info(f"{reason_str} — routing to finalize")
            return _route("finalize", reason_str)

        r = _term(state["api_calls"] >= config.max_iterations,
                  f"max_api_calls ({state['api_calls']}/{config.max_iterations})")
        if r: return r

        r = _term(state["iteration"] > config.max_iterations,
                  f"max_iterations ({state['iteration']}/{config.max_iterations})")
        if r: return r

        r = _term(state["consecutive_failures"] >= config.max_retries,
                  f"max_retries ({state['consecutive_failures']}/{config.max_retries})")
        if r: return r

        r = _term(state["no_progress_count"] >= config.max_no_progress,
                  f"max_no_progress ({state['no_progress_count']}/{config.max_no_progress})")
        if r: return r

        # Check context window limit
        token_count = count_message_tokens(state["messages"], config.model)
        r = _term(token_count >= config.context_window,
                  f"context_window_limit ({token_count:,}/{config.context_window:,})")
        if r: return r

        # Continue to agent
        return _route("agent", "continue")

    graph.add_conditional_edges(
        "prune_context",
        route_after_update,
        {
            "agent":            "agent",
            "finalize":         "finalize",
            "phase_transition": "phase_transition",
            END:                END,
        }
    )

    return graph.compile()
