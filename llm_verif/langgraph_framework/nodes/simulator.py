"""
Simulator Node

Wraps the existing Simulator class (QuestaSim/Verilator) for LangGraph integration.
This is not an agent (no LLM calls), but a deterministic execution node.
"""

import logging
import os
from typing import Dict, Any, Optional
from llm_verif.langgraph_framework.state import VerificationState
from llm_verif.record import Record


def simulator_node(state: VerificationState, simulator, environment, record: Optional[Record] = None) -> Dict[str, Any]:
    """
    Simulator Node: Execute testbench and collect coverage.

    This wraps the existing Simulator abstraction (QuestaSim or Verilator).

    Args:
        state: Current verification state
        simulator: Simulator instance (QuestaSim or Verilator)
        environment: Environment with design info

    Returns:
        State update with simulation_results, max_coverage, coverage_history
    """
    logging.info("[Simulator Node] Running simulation...")

    testbench = state.get("current_testbench", "")
    iteration = state.get("iteration", 0)

    if not testbench:
        logging.error("[Simulator Node] No testbench to simulate!")
        return {
            "simulation_results": {
                "success": False,
                "error_code": 4,
                "error_message": "Empty testbench",
                "coverage": 0.0
            },
            "simulation_success": False,
            "simulator_calls": state.get("simulator_calls", 0)
        }

    try:
        # Create testbench file name stem
        tb_stem = f"tb_llm_{state['design_name']}_{state['run_index']}_{iteration}_0"
        sim_runs = state.get("sim_runs", 1)
        work_dir = state.get("work_dir", environment.work_dir)

        # Plan artifacts (creates file paths)
        artifact_plan = simulator.plan_artifacts(work_dir, tb_stem, sim_runs)

        # Ensure directory exists before writing file
        os.makedirs(os.path.dirname(artifact_plan.tb_path), exist_ok=True)

        # Write testbench to file
        with open(artifact_plan.tb_path, "w+") as f:
            f.write(testbench)

        # Get design data point
        data_point = environment.dataset.get_data_point(state["design_name"])

        # Run simulation using existing simulator
        logging.info(f"[Simulator Node] Executing {tb_stem}...")

        cov_response = simulator.run_simulation_flow(
            work_dir=work_dir,
            tb_name=artifact_plan.tb_path.split('/')[-1],  # Just filename
            data_point=data_point,
            sim_runs=sim_runs
        )

        # Move artifacts to storage (like original system)
        if environment.store:
            for p in [
                artifact_plan.tb_path,
                artifact_plan.compile_log,
                *artifact_plan.sim_logs,
                *(artifact_plan.per_run_coverage_dbs or []),
                artifact_plan.merged_coverage_db,
                artifact_plan.report_path,
                artifact_plan.annotate_dir,
                artifact_plan.info_path
            ]:
                if p and os.path.exists(p):
                    environment.store.move(p)

        success = cov_response.success
        coverage = cov_response.total_coverage

        logging.info(
            f"[Simulator Node] Simulation {'PASSED' if success else 'FAILED'}: "
            f"{coverage:.2f}% coverage (error_code={cov_response.error_code})"
        )

        # Extract coverage feedback using simulator's method
        coverage_summary = ""
        coverage_feedback = ""

        if success:
            coverage_summary = simulator.format_coverage_summary(cov_response)
            coverage_feedback = simulator.extract_coverage_feedback(cov_response)

        # Update max coverage
        max_cov = max(state.get("max_coverage", 0.0), coverage)

        # Update valid iterations
        valid_iterations = state.get("valid_iterations", 0)
        if success:
            valid_iterations += 1

        # Update Record tracking (if provided)
        if record:
            from llm_verif.langgraph_framework.utils.record_integration import update_record_from_state
            update_record_from_state(record, state, cov_response)

        return {
            "simulation_results": {
                "success": success,
                "error_code": cov_response.error_code,
                "coverage": coverage,
                "coverage_list": cov_response.coverage_list,
                "error_message": cov_response.error_message,
                "coverage_summary": coverage_summary,
                "coverage_feedback": coverage_feedback
            },
            "simulation_success": success,
            "max_coverage": max_cov,
            "coverage_history": [coverage],
            "valid_iterations": valid_iterations,
            "simulator_calls": state.get("simulator_calls", 0) + 1
        }

    except Exception as e:
        logging.error(f"[Simulator Node] Error: {e}")
        return {
            "simulation_results": {
                "success": False,
                "error_code": 99,
                "coverage": 0.0,
                "error_message": f"Simulator exception: {str(e)}"
            },
            "simulation_success": False,
            "simulator_calls": state.get("simulator_calls", 0) + 1
        }
