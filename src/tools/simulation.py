from pathlib import Path
from typing import Dict, Any
from langchain.tools import tool
import logging

_config = None
_adapter = None  # Simulator adapter instance

def set_config(config):
    """Set config and initialize appropriate simulator adapter.

    This function now instantiates the correct adapter (QuestaSim or Verilator)
    based on the simulator_type in the config.
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

        # Resolve testbench path
        tb_path = (_config.work_dir / testbench_path).resolve()
        if not tb_path.exists():
            return {"success": False, "error": f"Testbench not found: {testbench_path}", "iteration": iteration, "retry": retry_num}

        # Get design files from config (includes both main design and context files)
        design_files = _config.design_files + _config.design_context_files

        # Delegate to adapter
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

        # Add user-friendly error summary if compilation failed
        if not result.get("success", False):
            stderr = result.get("stderr", "")
            stdout = result.get("stdout", "")
            error_output = stderr or stdout or "Unknown error"
            result["error_summary"] = f"Compilation failed. Check {log_name} for details.\n{error_output[:500]}"

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

        # Add user-friendly error summary if simulation failed
        if not result.get("success", False):
            error_msg = result.get("error", "")
            stderr = result.get("stderr", "")
            stdout = result.get("stdout", "")
            error_output = error_msg or stderr or stdout or "Unknown error"
            result["error_summary"] = f"Simulation failed. Check {log_name} for details.\n{error_output[:500]}"

        # Add iteration and retry info to result
        result["iteration"] = iteration
        result["retry"] = retry_num
        return result

    except Exception as e:
        logging.error(f"Simulation error: {e}")
        return {"success": False, "error": str(e)}
