"""Test Generator agent for CovAgent v2.

Each Test Generator is a stateless agent created fresh per dispatch via
create_agent. It receives a task description, writes a testbench, compiles,
simulates, and retries errors internally. It does NOT call parse_coverage —
it returns the coverage_db_path for the framework to handle.

Tool isolation: Each generator gets its own tool instances (closures) that
capture a generator-specific config. This enables parallel execution without
shared mutable state. Each generator uses its own QuestaSim work library
in sim_work/gen_{id}/.
"""

import json
import logging
import subprocess
from copy import copy
from pathlib import Path
from typing import Dict, Any, List, Optional

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from ...config import Config
from ...prompts.loader import load_generator_prompt
from ...utils.event_log import emit
from ...utils.conversation_logger import make_generator_logger


def _read_file_safe(path) -> str:
    """Read a file safely, returning empty string if not found."""
    if path and Path(path).exists():
        try:
            return Path(path).read_text(encoding='utf-8', errors='ignore')
        except Exception:
            pass
    return ""


def _list_uvm_tb_files(config) -> list:
    """List UVM testbench infrastructure files (fixed, not generated)."""
    files = []
    tb_dir = getattr(config, 'uvm_testbench_dir', None)
    seq_file = getattr(config, 'uvm_sequence_file', None)
    test_file = f"{config.uvm_test_name}.sv" if getattr(config, 'uvm_test_name', None) else None
    if tb_dir and Path(tb_dir).exists():
        for f in sorted(Path(tb_dir).iterdir()):
            if f.suffix == '.sv' and f.name != seq_file and f.name != test_file:
                files.append(str(f))
    return files


def make_generator_tools(
    config: Config,
    iteration: int,
    gen_id: int,
) -> list:
    """Create isolated tool instances for a test generator.

    Each tool closure captures generator-specific parameters (iteration, gen_id)
    and uses its own simulator adapter instance. This enables concurrent
    generators without shared mutable state.

    Args:
        config: Application configuration.
        iteration: Current orchestrator iteration.
        gen_id: Unique generator ID within this iteration.

    Returns:
        List of tool instances [write_file, compile_design, run_simulation].
    """
    # Generator-specific paths
    gen_sim_dir = config.work_dir / "sim_work" / f"gen_{gen_id}"
    gen_sim_dir.mkdir(parents=True, exist_ok=True)

    tb_dir = config.work_dir / "testbenches"
    tb_dir.mkdir(parents=True, exist_ok=True)

    log_dir = config.work_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    coverage_dir = config.work_dir / "coverage"
    coverage_dir.mkdir(parents=True, exist_ok=True)

    # Create generator-specific simulator adapter
    simulator_type = getattr(config, 'simulator_type', 'questasim').lower()
    if simulator_type == 'questasim':
        from ...simulators.questasim_adapter import QuestasimAdapter
        adapter = QuestasimAdapter(config.simulator_path)
    elif simulator_type == 'verilator':
        from ...simulators.verilator_adapter import VerilatorAdapter
        adapter = VerilatorAdapter(config.simulator_path)
    else:
        raise ValueError(f"Unsupported simulator type: {simulator_type}")

    # If UVM mode, pass UVM config to the adapter
    if getattr(config, 'uvm_enabled', False) and hasattr(adapter, 'set_uvm_config'):
        uvm_cfg = {
            'filelist': str(config.uvm_filelist),
            'top_module': config.uvm_top_module,
            'test_name': config.uvm_test_name,
            'dpi_lib': config.uvm_dpi_lib,
            'uvm_home': config.uvm_home,
            'testbench_dir': str(config.uvm_testbench_dir) if config.uvm_testbench_dir else None,
            'sequence_file': config.uvm_sequence_file,
        }
        adapter.set_uvm_config(uvm_cfg)
        logging.info(f"Generator {gen_id}: UVM config set on adapter")

    # Initialize QuestaSim work library in generator's sim directory
    if simulator_type == 'questasim':
        work_lib = gen_sim_dir / "work"
        if not work_lib.exists():
            try:
                vlib_cmd = [str(config.simulator_path / "vlib"), str(work_lib)]
                subprocess.run(vlib_cmd, capture_output=True, text=True, timeout=30)
                logging.info(f"Created work library for gen_{gen_id}")
            except Exception as e:
                logging.warning(f"Failed to create work library for gen_{gen_id}: {e}")

    # Mutable retry counter for this generator
    retry_state = {"compile_attempts": 0, "sim_attempts": 0}

    # --- Tool: write_file ---
    @tool
    def write_file(path: str, content: str) -> Dict[str, Any]:
        """Write content to a file in the work directory.

        Args:
            path: Relative path within the work directory (e.g., "testbenches/tb_iter_3_gen_0.sv")
            content: File content to write.

        Returns:
            Dictionary with success status.
        """
        try:
            file_path = (config.work_dir / path).resolve()
            # Security: ensure path is within work directory
            if not str(file_path).startswith(str(config.work_dir.resolve())):
                return {"success": False, "error": "Path must be within work directory"}
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {"success": True, "path": str(file_path), "size": len(content)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- Tool: compile_design ---
    @tool
    def compile_design(testbench_path: str) -> Dict[str, Any]:
        """Compile the testbench with all design files.

        Args:
            testbench_path: Path to testbench file (relative to work directory).

        Returns:
            Dictionary with success, return_code, stdout, stderr.
        """
        try:
            retry_state["compile_attempts"] += 1
            retry_num = retry_state["compile_attempts"]

            uvm_mode = getattr(config, 'uvm_enabled', False)
            func_cov_enabled = getattr(config, 'functional_coverage_enabled', False)

            if uvm_mode:
                # UVM mode: pre-compile validation then delegate entirely to adapter
                from ...validators.uvm_validator import validate_uvm_files
                passed, val_errors = validate_uvm_files(
                    work_dir=config.work_dir,
                    sequence_file=config.uvm_sequence_file,
                    test_name=config.uvm_test_name,
                    interface_name=getattr(config, 'uvm_interface_name', None),
                    env_class=getattr(config, 'uvm_env_class', None),
                    top_module=config.uvm_top_module,
                )
                if not passed:
                    fix_instructions = "\n".join(f"- {e}" for e in val_errors)
                    return {
                        "success": False,
                        "error": "Pre-compile validation failed. Fix these issues before compiling:",
                        "validation_errors": fix_instructions,
                        "stdout": f"STATIC VALIDATION FAILED ({len(val_errors)} issues):\n{fix_instructions}",
                    }
                tb_path = None
                design_files = []
                compile_deps_files = []
            else:
                tb_path = (config.work_dir / testbench_path).resolve()
                if not tb_path.exists():
                    return {"success": False, "error": f"Testbench not found: {testbench_path}"}

                design_files = config.design_context_files + config.design_files
                compile_deps_files = getattr(config, 'compile_deps_files', [])

                if func_cov_enabled:
                    func_cov_tb = getattr(config, 'functional_coverage_testbench_path', None)
                    if func_cov_tb:
                        from ...utils.questasim import inject_stimulus_into_template
                        injected_path = tb_path.parent / f"{tb_path.stem}_injected.sv"
                        try:
                            tb_path = inject_stimulus_into_template(func_cov_tb, tb_path, injected_path)
                        except ValueError as e:
                            return {"success": False, "error": str(e)}

            result = adapter.compile(
                testbench_path=tb_path,
                design_files=design_files,
                work_dir=gen_sim_dir,
                timeout=config.sim_timeout,
                compile_deps_files=compile_deps_files,
                functional_coverage=func_cov_enabled,
            )

            # Post-compile UVM verification
            if uvm_mode and result.get("success", False):
                from ...validators.uvm_validator import verify_compile_log
                post_ok, post_warnings = verify_compile_log(
                    stdout=result.get("stdout", ""),
                    stderr=result.get("stderr", ""),
                )
                if post_warnings:
                    warn_text = "\n".join(f"- {w}" for w in post_warnings)
                    result["success"] = False
                    result["error"] = "Post-compile verification failed"
                    result["post_compile_warnings"] = warn_text

            # Log naming: compile_iter_{N}_gen_{id}.log or _retry_{M}
            if retry_num == 1:
                log_name = f"compile_iter_{iteration}_gen_{gen_id}.log"
            else:
                log_name = f"compile_iter_{iteration}_gen_{gen_id}_retry_{retry_num}.log"

            log_path = log_dir / log_name
            with open(log_path, 'w') as f:
                f.write(f"=== COMPILATION: Iter {iteration}, Gen {gen_id}, Attempt {retry_num} ===\n")
                f.write(f"Testbench: {testbench_path}\n")
                f.write(f"Success: {result.get('success', False)}\n\n")
                f.write(f"STDOUT:\n{result.get('full_stdout', result.get('stdout', ''))}\n\n")
                f.write(f"STDERR:\n{result.get('full_stderr', result.get('stderr', ''))}\n")

            result["log_path"] = str(log_path)
            result.pop("full_stdout", None)
            result.pop("full_stderr", None)

            if result.get("success", False):
                result["stdout"] = f"Compilation successful. Log: {log_name}"
                result.pop("stderr", None)
            else:
                stderr = result.get("stderr", "")
                stdout = result.get("stdout", "")
                error_output = stderr or stdout or "Unknown error"
                result["error_summary"] = f"Compilation failed. Check {log_name}.\n{error_output[:500]}"
                result["stdout"] = adapter.filter_compile_output(result.get("stdout", ""))
                result["stderr"] = adapter.filter_compile_output(result.get("stderr", ""))

            return result

        except Exception as e:
            logging.error(f"Generator {gen_id} compile error: {e}")
            return {"success": False, "error": str(e)}

    # --- Tool: run_simulation ---
    @tool
    def run_simulation(testbench_name: str = "tb_llm", num_runs: int = None) -> Dict[str, Any]:
        """Run simulation with coverage collection.

        Args:
            testbench_name: Name of testbench module (default: "tb_llm").
            num_runs: Number of simulation runs with different seeds (default: from config).

        Returns:
            Dictionary with success, coverage_db_path, stdout.
        """
        try:
            if num_runs is None:
                num_runs = config.sim_runs

            retry_state["sim_attempts"] += 1
            retry_num = retry_state["sim_attempts"]

            result = adapter.simulate(
                testbench_name=testbench_name,
                num_runs=num_runs,
                work_dir=gen_sim_dir,
                iteration=iteration,
                timeout=config.sim_timeout,
            )

            # Move coverage DB to shared coverage dir with gen-specific naming
            if result.get("success") and result.get("coverage_db_path"):
                src_db = Path(result["coverage_db_path"])
                if src_db.exists():
                    dest_name = f"cov_iter_{iteration}_gen_{gen_id}.ucdb"
                    dest_db = coverage_dir / dest_name
                    import shutil
                    shutil.copy2(str(src_db), str(dest_db))
                    result["coverage_db_path"] = str(dest_db)
                    logging.info(f"Generator {gen_id} coverage saved to {dest_name}")

            # Log naming
            if retry_num == 1:
                log_name = f"sim_iter_{iteration}_gen_{gen_id}.log"
            else:
                log_name = f"sim_iter_{iteration}_gen_{gen_id}_retry_{retry_num}.log"

            log_path = log_dir / log_name
            with open(log_path, 'w') as f:
                f.write(f"=== SIMULATION: Iter {iteration}, Gen {gen_id}, Attempt {retry_num} ===\n")
                f.write(f"Testbench: {testbench_name}\n")
                f.write(f"Num Runs: {num_runs}\n")
                f.write(f"Success: {result.get('success', False)}\n\n")
                f.write(f"STDOUT:\n{result.get('stdout', '')}\n")
                if result.get("stderr"):
                    f.write(f"\nSTDERR:\n{result['stderr']}\n")

            result["log_path"] = str(log_path)

            if result.get("success", False):
                summary = (
                    f"{result.get('num_runs_completed', num_runs)}/{num_runs} "
                    f"runs successful. Log: {log_name}"
                )
                if result.get("warning"):
                    summary += f" Warning: {result['warning']}"
                result["stdout"] = summary
                result.pop("stderr", None)
            else:
                error_msg = result.get("error", "")
                stderr = result.get("stderr", "")
                stdout = result.get("stdout", "")
                error_output = error_msg or stderr or stdout or "Unknown error"
                result["error_summary"] = f"Simulation failed. Check {log_name}.\n{error_output[:500]}"
                result["stdout"] = adapter.filter_sim_output(result.get("stdout", ""))
                result["stderr"] = adapter.filter_sim_output(result.get("stderr", ""))

            return result

        except Exception as e:
            logging.error(f"Generator {gen_id} simulation error: {e}")
            return {"success": False, "error": str(e)}

    return [write_file, compile_design, run_simulation]


def dispatch_generator(
    config: Config,
    task_description: str,
    module_header: str,
    target_module: str,
    testplan_section: str,
    design_context: str,
    iteration: int,
    gen_id: int,
) -> dict:
    """Create and run a fresh Test Generator agent.

    Args:
        config: Application configuration.
        task_description: What stimulus to generate and why.
        module_header: Verilog module header for the target DUT.
        target_module: Module name being tested ("top" or submodule name).
        testplan_section: Relevant portion of the testplan.
        design_context: Analysis from the Design Expert.
        iteration: Current orchestrator iteration.
        gen_id: Unique generator ID.

    Returns:
        Dict with: success, summary, coverage_db_path, testbench_path, gen_id.
    """
    logging.info(f"Dispatching generator {gen_id} (iter {iteration}, "
                 f"target={target_module})")

    emit("generator_dispatch", {
        "gen_id": gen_id,
        "iteration": iteration,
        "target_module": target_module,
        "task_preview": task_description[:200],
    })

    try:
        # Create generator-specific tools
        gen_tools = make_generator_tools(config, iteration, gen_id)

        # Build LLM
        llm_kwargs = dict(
            model=config.test_generator_model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            api_key=config.openai_api_key,
        )
        if config.reasoning_effort != "disabled":
            llm_kwargs["reasoning_effort"] = config.reasoning_effort

        # Load system prompt (UVM-aware)
        uvm_kwargs = {}
        if getattr(config, 'uvm_enabled', False):
            uvm_kwargs = {
                'uvm_enabled': True,
                'uvm_seq_item_content': _read_file_safe(config.uvm_seq_item_file),
                'uvm_coverage_module_content': _read_file_safe(config.uvm_coverage_module_file),
                'uvm_sequence_file': config.uvm_sequence_file,
                'uvm_test_name': config.uvm_test_name,
                'uvm_testbench_files': _list_uvm_tb_files(config),
                'uvm_interface_name': getattr(config, 'uvm_interface_name', None),
                'uvm_env_class': getattr(config, 'uvm_env_class', None),
                'uvm_coverage_mode': config.uvm_coverage_mode,
            }
        system_prompt = load_generator_prompt(**uvm_kwargs)

        # Create fresh agent
        gen_agent = create_agent(
            model=ChatOpenAI(**llm_kwargs),
            tools=gen_tools,
            system_prompt=system_prompt,
            name=f"test_generator_{gen_id}",
        )

        # Build testbench path for this generator
        # In UVM mode the sequence/test filenames are fixed; use sequence file as tb_path
        if getattr(config, 'uvm_enabled', False):
            tb_filename = config.uvm_sequence_file
            tb_path = f"testbenches/{tb_filename}"
        else:
            tb_filename = f"tb_iter_{iteration}_gen_{gen_id}.sv"
            tb_path = f"testbenches/{tb_filename}"

        # Build task message
        task_parts = [
            f"## Task\n{task_description}",
            f"\n## Target Module: {target_module}",
            f"\n## Module Header\n```verilog\n{module_header}\n```",
        ]
        if design_context:
            task_parts.append(f"\n## Design Expert Analysis\n{design_context}")
        if testplan_section:
            task_parts.append(f"\n## Testplan Section\n{testplan_section}")
        func_cov_enabled = getattr(config, 'functional_coverage_enabled', False)
        func_cov_tb = getattr(config, 'functional_coverage_testbench_path', None)

        if func_cov_enabled and func_cov_tb:
            task_parts.append(
                f"\n## Functional Coverage Mode — STIMULUS BODY ONLY\n"
                f"Testbench template with covergroups: `{func_cov_tb}`. "
                f"Read it to understand the covergroup structure, port names, and sample event.\n"
                f"The framework injects your stimulus into the template automatically.\n\n"
                f"**Write ONLY the body lines** of the initial block to `{tb_path}` — "
                f"do NOT include `initial begin`, `$finish;`, `end`, or any module wrapper. "
                f"The framework adds these automatically."
            )
            task_parts.append(
                f"\n## Instructions\n"
                f"- Read the testbench template at `{func_cov_tb}` first\n"
                f"- Write ONLY the stimulus body lines to `{tb_path}` "
                f"(no `initial begin`, no `$finish;`, no `end`, no module)\n"
                f"- Compile with `compile_design(\"{tb_path}\")`\n"
                f"- Simulate with `run_simulation(testbench_name=\"tb_llm\")`\n"
                f"- If compile or simulation fails, fix and retry (max {config.gen_max_retries} total failures)\n"
                f"- On success, report the coverage database path from the simulation result\n"
                f"- Do NOT call parse_coverage — the framework handles coverage analysis"
            )
        else:
            task_parts.append(
                f"\n## Instructions\n"
                f"- Write your testbench to `{tb_path}`\n"
                f"- The testbench module MUST be named `tb_llm`\n"
                f"- Instantiate `{target_module}` as the DUT\n"
                f"- After writing, compile with `compile_design`, then simulate with `run_simulation`\n"
                f"- If compile or simulation fails, fix and retry (max {config.gen_max_retries} total failures)\n"
                f"- On success, report the coverage database path from the simulation result\n"
                f"- Do NOT call parse_coverage — the framework handles coverage analysis"
            )
        task_message = "\n".join(task_parts)

        # Invoke the generator agent
        # Recursion limit: generous to allow internal retries
        # gen_max_retries * ~6 steps per retry (think + write + think + compile + think + sim) + buffer
        recursion_limit = max(50, config.gen_max_retries * 10 + 20)

        result = gen_agent.invoke(
            {"messages": [HumanMessage(content=task_message)]},
            config={
                "recursion_limit": recursion_limit,
                "callbacks": [make_generator_logger(iteration, gen_id)],
            },
        )

        # Extract results from the generator's message history
        return _extract_generator_result(result, gen_id, iteration, target_module, tb_path)

    except Exception as e:
        error_msg = f"Generator {gen_id} dispatch error: {str(e)}"
        logging.error(error_msg)
        emit("generator_error", {
            "gen_id": gen_id,
            "iteration": iteration,
            "error": str(e),
        })
        return {
            "success": False,
            "summary": error_msg,
            "coverage_db_path": None,
            "testbench_path": None,
            "gen_id": gen_id,
            "target_module": target_module,
        }


def _extract_generator_result(
    result: dict,
    gen_id: int,
    iteration: int,
    target_module: str,
    tb_path: str,
) -> dict:
    """Extract structured results from the generator's final state.

    Scans the generator's message history for the last successful
    run_simulation ToolMessage to extract the coverage_db_path.
    """
    messages = result.get("messages", [])
    coverage_db_path = None
    success = False
    summary_parts = []

    # Scan for the last successful simulation result
    for msg in reversed(messages):
        if hasattr(msg, 'name') and msg.name == 'run_simulation':
            try:
                content = msg.content
                if isinstance(content, str):
                    parsed = json.loads(content)
                else:
                    parsed = content
                if isinstance(parsed, dict) and parsed.get("success"):
                    coverage_db_path = parsed.get("coverage_db_path")
                    success = True
                    break
            except (json.JSONDecodeError, TypeError):
                continue

    # Extract the generator's final message as summary
    for msg in reversed(messages):
        if type(msg).__name__ == 'AIMessage' and hasattr(msg, 'content') and msg.content:
            summary_parts.append(msg.content[:500])
            break

    if not summary_parts:
        summary_parts.append("Generator completed without a final summary message.")

    summary = summary_parts[0]

    gen_result = {
        "success": success,
        "summary": summary,
        "coverage_db_path": coverage_db_path,
        "testbench_path": tb_path if success else None,
        "gen_id": gen_id,
        "target_module": target_module,
    }

    emit("generator_result", {
        "gen_id": gen_id,
        "iteration": iteration,
        "success": success,
        "coverage_db_path": coverage_db_path,
        "summary_preview": summary[:200],
    })

    logging.info(f"Generator {gen_id} result: "
                 f"{'SUCCESS' if success else 'FAILED'}"
                 f"{f' coverage_db={coverage_db_path}' if coverage_db_path else ''}")

    return gen_result
