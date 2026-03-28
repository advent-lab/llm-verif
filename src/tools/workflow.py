"""Composite verification workflow tool.

Combines write_file, compile_design, run_simulation, and parse_coverage
into a single tool call to eliminate unnecessary LLM round-trips.
"""

import json
import logging
from typing import Any, Dict

from langchain.tools import tool

_config = None


def set_config(config):
    """Set config reference for workflow tools."""
    global _config
    _config = config


def _ensure_dict(result) -> dict:
    """Ensure a tool .invoke() result is a dict (handles JSON string returns)."""
    if isinstance(result, str):
        try:
            return json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return {"success": False, "error": result}
    return result if isinstance(result, dict) else {"success": False, "error": str(result)}


@tool
def run_verification_cycle(
    testbench_path: str,
    testbench_content: str,
    testbench_name: str = "tb_llm",
    num_runs: int = None,
) -> Dict[str, Any]:
    """Write a testbench, compile, simulate, and parse coverage in one step.

    This is the recommended tool for a full verification iteration. It runs
    the complete pipeline and returns all results at once. If any stage fails,
    it stops early and returns the error context for that stage.

    Use individual tools (compile_design, run_simulation, parse_coverage) only
    for targeted retries after fixing a specific error.

    Args:
        testbench_path: Relative path for testbench file (e.g., "testbenches/tb_iter_1.sv")
        testbench_content: Full SystemVerilog testbench source code
        testbench_name: Testbench module name (default: "tb_llm")
        num_runs: Number of simulation runs with different seeds (default: from config)

    Returns:
        Dictionary with:
        - stopped_at: str - last stage reached ("write", "compile", "simulate", "coverage")
        - success: bool - True only if ALL stages succeeded
        - write_result: dict - result from writing the testbench file
        - compile_result: dict - result from compilation (if write succeeded)
        - sim_result: dict - result from simulation (if compile succeeded)
        - coverage_result: dict - result from coverage parsing (if sim succeeded)
        - error_stage: str - stage that failed (only present on failure)
        - error_summary: str - human-readable error description (only present on failure)
    """
    # Lazy imports to avoid circular dependencies
    from .filesystem import write_file as _write_file
    from .simulation import compile_design as _compile, run_simulation as _sim
    from .analysis import parse_coverage as _coverage

    result = {
        "stopped_at": None,
        "success": False,
    }

    # Stage 1: Write testbench file
    logging.info(f"[verification_cycle] Stage 1/4: Writing testbench to {testbench_path}")
    write_result = _ensure_dict(_write_file.invoke({"path": testbench_path, "content": testbench_content}))
    result["write_result"] = write_result
    result["stopped_at"] = "write"
    if not write_result.get("success"):
        result["error_stage"] = "write"
        result["error_summary"] = f"File write failed: {write_result.get('error', 'unknown')}"
        logging.warning(f"[verification_cycle] Write failed: {result['error_summary']}")
        return result

    # Stage 2: Compile design with testbench
    logging.info(f"[verification_cycle] Stage 2/4: Compiling design")
    compile_result = _ensure_dict(_compile.invoke({"testbench_path": testbench_path}))
    result["compile_result"] = compile_result
    result["stopped_at"] = "compile"
    if not compile_result.get("success"):
        result["error_stage"] = "compile"
        result["error_summary"] = compile_result.get(
            "error_summary",
            f"Compilation failed. Check {compile_result.get('log_path', 'compile log')} for details.",
        )
        logging.warning(f"[verification_cycle] Compile failed at iter {compile_result.get('iteration', '?')}")
        return result

    # Stage 3: Run simulation
    logging.info(f"[verification_cycle] Stage 3/4: Running simulation")
    sim_args = {"testbench_name": testbench_name}
    if num_runs is not None:
        sim_args["num_runs"] = num_runs
    sim_result = _ensure_dict(_sim.invoke(sim_args))
    result["sim_result"] = sim_result
    result["stopped_at"] = "simulate"
    if not sim_result.get("success"):
        result["error_stage"] = "simulate"
        result["error_summary"] = sim_result.get(
            "error_summary",
            f"Simulation failed. Check {sim_result.get('log_path', 'simulation log')} for details.",
        )
        logging.warning(f"[verification_cycle] Simulation failed at iter {sim_result.get('iteration', '?')}")
        return result

    # Stage 4: Parse coverage
    coverage_db = sim_result.get("coverage_db_path")
    if not coverage_db:
        result["error_stage"] = "coverage"
        result["error_summary"] = "No coverage database path returned from simulation"
        logging.warning("[verification_cycle] No coverage_db_path in simulation result")
        return result

    logging.info(f"[verification_cycle] Stage 4/4: Parsing coverage from {coverage_db}")
    coverage_result = _ensure_dict(_coverage.invoke({"coverage_db_path": coverage_db}))
    result["coverage_result"] = coverage_result
    result["stopped_at"] = "coverage"
    if not coverage_result.get("success"):
        result["error_stage"] = "coverage"
        result["error_summary"] = f"Coverage parsing failed: {coverage_result.get('error', 'unknown')}"
        logging.warning(f"[verification_cycle] Coverage parsing failed")
        return result

    # All stages succeeded
    result["success"] = True
    cumulative = coverage_result.get("cumulative_coverage", coverage_result.get("total_coverage", 0))
    iteration = coverage_result.get("iteration_coverage", coverage_result.get("total_coverage", 0))
    logging.info(
        f"[verification_cycle] Complete — iteration coverage: {iteration:.2f}%, "
        f"cumulative coverage: {cumulative:.2f}%"
    )
    return result
