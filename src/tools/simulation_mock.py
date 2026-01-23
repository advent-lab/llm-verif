"""Mock simulation tools for testing without QuestaSim.

This module provides mock implementations of compile_design() and run_simulation()
that simulate QuestaSim behavior without requiring the actual simulator.
"""

from pathlib import Path
from typing import Dict, Any
from langchain.tools import tool
import logging
import time
import random

_config = None

def set_config(config):
    """Set global config for tools."""
    global _config
    _config = config


@tool
def compile_design(testbench_path: str) -> Dict[str, Any]:
    """
    MOCK: Simulate testbench compilation.

    Validates that testbench file exists and has basic syntax.
    Returns success after brief delay to simulate compilation.

    Args:
        testbench_path: Path to testbench file (relative to work_dir)

    Returns:
        Dict with success status, stdout, stderr, and log_path
    """
    try:
        # Verify testbench exists
        tb_path = (_config.work_dir / testbench_path).resolve()
        if not tb_path.exists():
            return {
                "success": False,
                "error": f"Testbench not found: {testbench_path}"
            }

        # Read and validate basic syntax
        with open(tb_path, 'r') as f:
            content = f.read()

        # Simple validation checks
        if "module tb_llm" not in content:
            return {
                "success": False,
                "error": "Testbench must define 'module tb_llm'"
            }

        if "$finish" not in content:
            return {
                "success": False,
                "error": "Testbench missing $finish statement"
            }

        # Check for basic SystemVerilog structure
        if "endmodule" not in content:
            return {
                "success": False,
                "error": "Testbench missing 'endmodule' statement"
            }

        # Simulate compilation delay
        time.sleep(0.5)

        # Infer current iteration by counting existing log files
        log_dir = _config.work_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        existing_logs = list(log_dir.glob("compile_iter_*.log"))
        iteration = len(existing_logs) + 1

        # Create mock log
        log_path = log_dir / f"compile_iter_{iteration}.log"

        mock_output = f"""# QuestaSim Mock Compilation
# Reading: {testbench_path}
# Syntax check: PASSED
# Errors: 0, Warnings: 0
#
# MOCK MODE: No actual compilation performed
# This is a syntax validation only
"""
        with open(log_path, 'w') as f:
            f.write(mock_output)

        logging.info(f"MOCK: Compiled {testbench_path} (syntax validated)")

        return {
            "success": True,
            "return_code": 0,
            "stdout": mock_output,
            "stderr": "",
            "log_path": str(log_path)
        }

    except Exception as e:
        logging.error(f"Mock compilation error: {e}")
        return {"success": False, "error": str(e)}


@tool
def run_simulation(testbench_name: str = "tb_llm", num_runs: int = None) -> Dict[str, Any]:
    """
    MOCK: Simulate test execution.

    Creates mock UCDB files and simulates progressive coverage improvement.

    Args:
        testbench_name: Name of testbench module (default: "tb_llm")
        num_runs: Number of simulation runs (uses config default if not specified)

    Returns:
        Dict with success status, coverage_db_path, log_path, and num_runs_completed
    """
    try:
        if num_runs is None:
            num_runs = _config.sim_runs

        # Infer current iteration by counting existing UCDB files
        coverage_dir = _config.work_dir / "coverage"
        coverage_dir.mkdir(parents=True, exist_ok=True)
        existing_ucdbs = list(coverage_dir.glob("iter_*.ucdb"))
        iteration = len(existing_ucdbs) + 1

        # Simulate multiple runs with progressive coverage improvement
        # First iteration: 50-60% coverage
        # Later iterations: increases by ~10% per iteration
        # Max out around 95-100% at iteration 5+
        base_coverage = min(50 + (iteration * 10), 90)
        coverage_pct = base_coverage + random.randint(0, 10)

        # Create mock UCDB file with metadata
        ucdb_path = coverage_dir / f"iter_{iteration}.ucdb"
        ucdb_metadata = f"""MOCK UCDB File
Iteration: {iteration}
Coverage: {coverage_pct}%
Runs: {num_runs}
Testbench: {testbench_name}
Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}
"""
        ucdb_path.write_text(ucdb_metadata)

        # Create mock simulation log
        log_path = _config.work_dir / "logs" / f"sim_iter_{iteration}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        mock_output = f"""# QuestaSim Mock Simulation
# Testbench: {testbench_name}
# Runs: {num_runs}
# Coverage: {coverage_pct}%
# Errors: 0, Warnings: 0
#
# MOCK MODE: No actual simulation performed
# Coverage values are simulated for testing
#
# Run 1/{num_runs}: PASS
# Run 2/{num_runs}: PASS
# ... (remaining runs)
# Run {num_runs}/{num_runs}: PASS
#
# All runs completed successfully
# Coverage database: {ucdb_path.name}
"""
        with open(log_path, 'w') as f:
            f.write(mock_output)

        logging.info(f"MOCK: Simulated {num_runs} runs, coverage: {coverage_pct}%")

        # Simulate delay (shorter than real simulation)
        time.sleep(1.0)

        return {
            "success": True,
            "stdout": mock_output,
            "stderr": "",
            "coverage_db_path": str(ucdb_path),
            "log_path": str(log_path),
            "num_runs_completed": num_runs
        }

    except Exception as e:
        logging.error(f"Mock simulation error: {e}")
        return {"success": False, "error": str(e)}
