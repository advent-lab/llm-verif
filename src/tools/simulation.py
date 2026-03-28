from pathlib import Path
from typing import Dict, Any
from langchain.tools import tool
import logging
import os

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
    Automatically enables functional coverage flags if FUNCTIONAL_COVERAGE_ENABLED=1.

    Args:
        testbench_path: Path to testbench file (relative to work directory)

    Returns:
        Dictionary with success, return_code, stdout, stderr, log_path

    The compiler automatically includes all RTL files from the design directory.
    Coverage instrumentation:
    - Code coverage mode: Statement coverage (QuestaSim) or line coverage (Verilator)
    - Functional coverage mode: Full coverage including functional bins (+cover=sbfec)
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

        # In UVM mode, the .f file lists everything; testbench_path is just for logging.
        # In standard mode, resolve the testbench path relative to work_dir.
        uvm_mode = getattr(_config, 'uvm_enabled', False)

        if uvm_mode:
            # ── Pre-compile static validation (zero tokens, zero compile cost) ──
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

            tb_path = None  # Not used; .f file covers all sources
            design_files = []
        else:
            tb_path = (_config.work_dir / testbench_path).resolve()
            if not tb_path.exists():
                return {"success": False, "error": f"Testbench not found: {testbench_path}", "iteration": iteration, "retry": retry_num}
            design_files = _config.design_files + _config.design_context_files

        # Delegate to adapter (adapter checks FUNCTIONAL_COVERAGE_ENABLED env var
        # and UVM config internally)
        result = _adapter.compile(
            testbench_path=tb_path,
            design_files=design_files,
            work_dir=_config.work_dir,
            timeout=_config.sim_timeout
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
            f.write(f"STDOUT:\n{result.get('stdout', '(empty)')}\n\n")
            f.write(f"STDERR:\n{result.get('stderr', '(empty)')}\n")
        result["log_path"] = str(log_path)

        # ── Post-compile UVM verification ─────────────────────────────────
        if uvm_mode and result.get("success", False):
            from ..validators.uvm_validator import verify_compile_log
            post_ok, post_warnings = verify_compile_log(
                stdout=result.get("stdout", ""),
                stderr=result.get("stderr", ""),
            )
            if not post_warnings:
                logging.info("UVM post-compile verification: PASSED")
            else:
                warn_text = "\n".join(f"- {w}" for w in post_warnings)
                logging.warning(f"UVM post-compile warnings:\n{warn_text}")
                # These are blocking — dual-UVM or stale binary will crash sim
                result["success"] = False
                result["error"] = "Post-compile verification failed"
                result["stdout"] = (
                    f"Compilation succeeded but UVM verification failed:\n{warn_text}\n"
                    f"Full log: {log_name}"
                )
                result["stderr"] = ""

        # Summarize output for the LLM (full output already saved to log file)
        if result.get("success", False):
            result["stdout"] = f"Compilation successful. Full log: {log_name}"
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
    In functional coverage mode, automatically generates a text coverage report.

    Args:
        testbench_name: Name of testbench module (default: "tb_llm")
        num_runs: Number of simulation runs with different random seeds (default: from config)

    Returns:
        Dictionary with success, stdout, stderr, coverage_db_path, log_path
        If functional coverage mode: Also includes functional_coverage_report_path

    Multiple runs help achieve better random coverage.
    For QuestaSim: Coverage databases are automatically merged.
    For Verilator: Coverage accumulates to a single .dat file.
    
    FUNCTIONAL COVERAGE MODE:
    If FUNCTIONAL_COVERAGE_ENABLED=1, this tool also generates a text-based
    functional coverage report using vcover report -details.
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

        # If functional coverage is enabled, generate text report
        funcov_enabled = getattr(_config, 'functional_coverage_enabled', False)
        if funcov_enabled and result.get("success", False):
            ucdb_path = Path(result.get("coverage_db_path"))
            if ucdb_path and ucdb_path.exists():
                funcov_report_path = _generate_functional_coverage_report(ucdb_path, iteration)
                if funcov_report_path:
                    result["functional_coverage_report_path"] = str(funcov_report_path)
                    logging.info(f"Generated functional coverage report: {funcov_report_path}")

        # Summarize output for the LLM (full output already saved to log file)
        if result.get("success", False):
            result["stdout"] = (
                f"Simulation completed: {result.get('num_runs_completed', num_runs)}/{num_runs} "
                f"runs successful. Full log: {log_name}"
            )
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


def _generate_functional_coverage_report(ucdb_path: Path, iteration: int) -> Path:
    """
    Generate text-based functional coverage report.
    
    Args:
        ucdb_path: Path to coverage database (.ucdb)
        iteration: Current iteration number
    
    Returns:
        Path to generated text report, or None if generation failed
    """
    try:
        from ..simulators.questasim_adapter import generate_functional_coverage_report
        
        coverage_dir = ucdb_path.parent
        report_path = coverage_dir / f"functional_coverage_iter_{iteration}.txt"
        
        success = generate_functional_coverage_report(
            simulator_path=_config.simulator_path,
            ucdb_path=ucdb_path,
            output_txt=report_path
        )
        
        if success:
            return report_path
        else:
            logging.error("Functional coverage report generation failed")
            return None
    
    except Exception as e:
        logging.error(f"Error generating functional coverage report: {e}")
        return None