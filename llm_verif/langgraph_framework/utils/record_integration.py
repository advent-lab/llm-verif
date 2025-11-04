"""
Record Integration for LangGraph

Helper functions to integrate LangGraph state with the existing Record tracking system.
"""

import logging
from llm_verif.simulator import CoverageResponse
from llm_verif.record import Record
from llm_verif.langgraph_framework.state import VerificationState


def update_record_from_state(
    record: Record,
    state: VerificationState,
    cov_response: CoverageResponse
) -> None:
    """
    Update Record dataframe from LangGraph state and coverage response.

    This mirrors the original system's record.update_dataframe() calls.

    Args:
        record: Record instance to update
        state: Current LangGraph state
        cov_response: Coverage response from simulator
    """
    run = state.get("run_index", 0)
    iteration = state.get("iteration", 0)
    batch_num = 0  # LangGraph evaluates candidates differently
    temperature = state.get("temperature", 0.7)
    top_p = 0.7  # Default from original system

    # Tokens and time from state (accumulated)
    tokens = state.get("tokens_generated", 0)
    gen_time = state.get("total_generation_time", 0.0)

    try:
        record.update_dataframe(
            coverage=cov_response,
            temperature=temperature,
            top_p=top_p,
            run=run,
            iteration=iteration,
            batch_num=batch_num,
            tokens=tokens,
            time=gen_time
        )
        logging.debug(f"[Record] Updated dataframe for run {run}, iteration {iteration}")
    except Exception as e:
        logging.warning(f"[Record] Failed to update dataframe: {e}")


def finalize_run_record(record: Record, run_index: int) -> None:
    """
    Finalize record for a completed run.

    Args:
        record: Record instance
        run_index: Index of the completed run
    """
    try:
        record.update_run_max_coverage(run_index)
        record.update_run_average_total_coverage(run_id=run_index)
        logging.info(f"[Record] Finalized run {run_index}")
    except Exception as e:
        logging.warning(f"[Record] Failed to finalize run: {e}")


def save_record(record: Record, csv_path: str) -> None:
    """
    Save record to CSV file.

    Args:
        record: Record instance
        csv_path: Path to save CSV
    """
    try:
        record.write_to_csv(csv_path)
        logging.info(f"[Record] Saved to {csv_path}")
    except Exception as e:
        logging.error(f"[Record] Failed to save to {csv_path}: {e}")
