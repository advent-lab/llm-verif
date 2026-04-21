from pathlib import Path
from typing import Dict, Any
from langchain.tools import tool
import logging

_config = None
_adapter = None  # Simulator adapter instance

def set_config(config):
    """Set config and initialize appropriate simulator adapter.

    This function now instantiates the correct adapter (QuestaSim or Verilator)
    based on the simulator_type in the config. If UVM mode is enabled, passes
    UVM configuration to the adapter.
    """
    global _config, _adapter
    _config = config

    # Factory pattern: select adapter based on config
    simulator_type = getattr(config, 'simulator_type', 'questasim').lower()

    if simulator_type == 'questasim':
        from ..simulators.questasim_adapter import QuestasimAdapter
        _adapter = QuestasimAdapter(config.simulator_path)
        logging.info("Initialized QuestaSim adapter")
    elif simulator_type == 'verilator':
        from ..simulators.verilator_adapter import VerilatorAdapter
        _adapter = VerilatorAdapter(config.simulator_path)
        logging.info("Initialized Verilator adapter")
    else:
        raise ValueError(f"Unsupported simulator type: {simulator_type}")

    # If UVM mode, pass UVM config to the adapter
    if getattr(config, 'uvm_enabled', False) and hasattr(_adapter, 'set_uvm_config'):
        uvm_cfg = {
            'filelist': str(config.uvm_filelist),
            'top_module': config.uvm_top_module,
            'test_name': config.uvm_test_name,
            'dpi_lib': config.uvm_dpi_lib,
            'uvm_home': config.uvm_home,
            'testbench_dir': str(config.uvm_testbench_dir) if config.uvm_testbench_dir else None,
            'sequence_file': config.uvm_sequence_file,
        }
        _adapter.set_uvm_config(uvm_cfg)

@tool
def compile_design(testbench_path: str) -> Dict[str, Any]:
    """
    Compile the testbench with all design files.

    Supports both QuestaSim and Verilator based on configuration.

    Args:
        testbench_path: Path to testbench file (relative to work directory)

    Returns:
        Dictionary with success, return_code, stdout, stderr, log_path

    The compiler automatically includes all RTL files from the design directory.
    Coverage instrumentation is enabled (statement coverage for QuestaSim,
    line coverage for Verilator).
    """
    try:
        # Get current iteration for naming
        iteration = _config.current_iteration

        # Reset compile attempt counter if iteration changed
        if _config._last_iter_for_compile != iteration:
            _config.compile_attempts_this_iter = 0
            _config._last_iter_for_compile = iteration

        # Increment compile attempt for this iteration
        _config.compile_attempts_this_iter += 1
        retry_num = _config.compile_attempts_this_iter

        uvm_mode = getattr(_config, 'uvm_enabled', False)

        if uvm_mode:
            # In UVM mode: pre-compile static validation before calling vlog
            from ..validators.uvm_validator import validate_uvm_files
            passed, val_errors = validate_uvm_files(
                work_dir=_config.work_dir,
                sequence_file=_config.uvm_sequence_file,
                test_name=_config.uvm_test_name,
                interface_name=getattr(_config, 'uvm_interface_name', None),
                env_class=getattr(_config, 'uvm_env_class', None),
                top_module=_config.uvm_top_module,
            )
            if not passed:
                fix_instructions = "\n".join(f"- {e}" for e in val_errors)
                logging.warning(f"UVM pre-compile validation failed:\n{fix_instructions}")
                return {
                    "success": False,
                    "error": "Pre-compile validation failed. Fix these issues before compiling:",
                    "validation_errors": fix_instructions,
                    "stdout": f"STATIC VALIDATION FAILED ({len(val_errors)} issues):\n{fix_instructions}",
                    "iteration": iteration,
                    "retry": retry_num,
                }
            tb_path = None
            design_files = []
            compile_deps_files = []
        else:
            # Resolve testbench path
            tb_path = (_config.work_dir / testbench_path).resolve()
            if not tb_path.exists():
                return {"success": False, "error": f"Testbench not found: {testbench_path}", "iteration": iteration, "retry": retry_num}

            # Get design files from config
            design_files = _config.design_context_files + _config.design_files
            compile_deps_files = getattr(_config, 'compile_deps_files', [])

            # Functional coverage: inject the agent's stimulus body into the template.
            func_cov_enabled = getattr(_config, 'functional_coverage_enabled', False)
            if func_cov_enabled:
                func_cov_tb = getattr(_config, 'functional_coverage_testbench_path', None)
                if func_cov_tb:
                    from ..utils.questasim import inject_stimulus_into_template
                    injected_path = tb_path.parent / f"{tb_path.stem}_injected.sv"
                    try:
                        tb_path = inject_stimulus_into_template(func_cov_tb, tb_path, injected_path)
                    except ValueError as e:
                        return {"success": False, "error": str(e)}

        # Delegate to adapter
        func_cov_enabled = getattr(_config, 'functional_coverage_enabled', False)
        result = _adapter.compile(
            testbench_path=tb_path,
            design_files=design_files,
            work_dir=_config.work_dir,
            timeout=_config.sim_timeout,
            compile_deps_files=compile_deps_files,
            functional_coverage=func_cov_enabled
        )

        # Build log filename: compile_iter_N.log or compile_iter_N_retry_M.log
        if retry_num == 1:
            log_name = f"compile_iter_{iteration}.log"
        else:
            log_name = f"compile_iter_{iteration}_retry_{retry_num}.log"

        log_path = _config.work_dir / "logs" / log_name
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, 'w') as f:
            f.write(f"=== COMPILATION: Iteration {iteration}, Attempt {retry_num} ===\n")
            f.write(f"Testbench: {testbench_path}\n")
            f.write(f"Success: {result.get('success', False)}\n")
            f.write(f"Return Code: {result.get('return_code', 'N/A')}\n\n")
            # Prefer full_stdout/full_stderr (includes dep output) for disk log
            f.write(f"STDOUT:\n{result.get('full_stdout', result.get('stdout', '(empty)'))}\n\n")
            f.write(f"STDERR:\n{result.get('full_stderr', result.get('stderr', '(empty)'))}\n")
        result["log_path"] = str(log_path)
        # Drop full_* keys so they don't leak into LLM-facing result
        result.pop("full_stdout", None)
        result.pop("full_stderr", None)

        # Post-compile UVM verification (checks for dual-UVM conflicts, stale binaries)
        if uvm_mode and result.get("success", False):
            from ..validators.uvm_validator import verify_compile_log
            post_ok, post_warnings = verify_compile_log(
                stdout=result.get("stdout", ""),
                stderr=result.get("stderr", ""),
            )
            if post_warnings:
                warn_text = "\n".join(f"- {w}" for w in post_warnings)
                logging.warning(f"UVM post-compile warnings:\n{warn_text}")
                result["success"] = False
                result["error"] = "Post-compile verification failed"
                result["post_compile_warnings"] = warn_text

        # Summarize output for the LLM (full output already saved to log file)
        if result.get("success", False):
            result["stdout"] = f"Full log: {log_name}"
            result.pop("stderr", None)
        else:
            stderr = result.get("stderr", "")
            stdout = result.get("stdout", "")
            error_output = stderr or stdout or "Unknown error"
            result["error_summary"] = f"Compilation failed. Check {log_name} for details.\n{error_output[:500]}"
            result["stdout"] = _adapter.filter_compile_output(result.get("stdout", ""))
            result["stderr"] = _adapter.filter_compile_output(result.get("stderr", ""))

        # Add iteration and retry info to result
        result["iteration"] = iteration
        result["retry"] = retry_num
        return result

    except Exception as e:
        logging.error(f"Compilation error: {e}")
        return {"success": False, "error": str(e)}

@tool
def run_simulation(testbench_name: str = "tb_llm", num_runs: int = None) -> Dict[str, Any]:
    """
    Run simulation with coverage collection.

    Supports both QuestaSim and Verilator based on configuration.

    Args:
        testbench_name: Name of testbench module (default: "tb_llm")
        num_runs: Number of simulation runs with different random seeds (default: from config)

    Returns:
        Dictionary with success, stdout, stderr, coverage_db_path, log_path

    Multiple runs help achieve better random coverage.
    For QuestaSim: Coverage databases are automatically merged.
    For Verilator: Coverage accumulates to a single .dat file.
    """
    try:
        if num_runs is None:
            num_runs = _config.sim_runs

        # Get current iteration for naming
        iteration = _config.current_iteration

        # Reset sim attempt counter if iteration changed
        if _config._last_iter_for_sim != iteration:
            _config.sim_attempts_this_iter = 0
            _config._last_iter_for_sim = iteration

        # Increment sim attempt for this iteration
        _config.sim_attempts_this_iter += 1
        retry_num = _config.sim_attempts_this_iter

        # Delegate to adapter - pass iteration for coverage file naming
        result = _adapter.simulate(
            testbench_name=testbench_name,
            num_runs=num_runs,
            work_dir=_config.work_dir,
            iteration=iteration,  # Use iteration for coverage file naming
            timeout=_config.sim_timeout
        )

        # Build log filename: sim_iter_N.log or sim_iter_N_retry_M.log
        if retry_num == 1:
            log_name = f"sim_iter_{iteration}.log"
        else:
            log_name = f"sim_iter_{iteration}_retry_{retry_num}.log"

        log_path = _config.work_dir / "logs" / log_name
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, 'w') as f:
            f.write(f"=== SIMULATION: Iteration {iteration}, Attempt {retry_num} ===\n")
            f.write(f"Testbench: {testbench_name}\n")
            f.write(f"Num Runs: {num_runs}\n")
            f.write(f"Success: {result.get('success', False)}\n\n")
            f.write(f"STDOUT:\n{result.get('stdout', '(empty)')}\n")
            if result.get("stderr"):
                f.write(f"\nSTDERR:\n{result.get('stderr', '(empty)')}\n")
        result["log_path"] = str(log_path)

        # Summarize output for the LLM (full output already saved to log file)
        if result.get("success", False):
            summary = (
                f"{result.get('num_runs_completed', num_runs)}/{num_runs} "
                f"runs successful."
            )
            if result.get("warning"):
                summary += f" Warning: {result['warning']}"
            summary += f" Full log: {log_name}"
            result["stdout"] = summary
            result.pop("stderr", None)
        else:
            error_msg = result.get("error", "")
            stderr = result.get("stderr", "")
            stdout = result.get("stdout", "")
            error_output = error_msg or stderr or stdout or "Unknown error"
            result["error_summary"] = f"Simulation failed. Check {log_name} for details.\n{error_output[:500]}"
            result["stdout"] = _adapter.filter_sim_output(result.get("stdout", ""))
            result["stderr"] = _adapter.filter_sim_output(result.get("stderr", ""))

        # Add iteration and retry info to result
        result["iteration"] = iteration
        result["retry"] = retry_num
        return result

    except Exception as e:
        logging.error(f"Simulation error: {e}")
        return {"success": False, "error": str(e)}
