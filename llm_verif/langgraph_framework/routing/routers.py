"""
Router Functions for LangGraph Conditional Edges

These functions determine the flow through the graph based on state.
"""

import logging
from typing import Literal
from llm_verif.langgraph_framework.state import VerificationState


def initial_router(state: VerificationState) -> Literal["planner", "generator"]:
    """
    Route from entry point to either Planner or Generator.

    Args:
        state: Current state

    Returns:
        "planner" if testplan enabled, otherwise "generator"
    """
    if state.get("testplan_enabled", False) and not state.get("plan_available", False):
        logging.info("[Initial Router] → planner (testplan enabled)")
        return "planner"
    else:
        logging.info("[Initial Router] → generator (skip planning)")
        return "generator"


def critique_router(state: VerificationState) -> Literal["approve", "revise", "reject"]:
    """
    Route based on Critic assessment.

    Flow:
    - approve → Simulator (looks good, proceed)
    - revise → Refiner (minor issues, fix)
    - reject → Generator (major issues, regenerate)

    Args:
        state: Current state

    Returns:
        Routing decision based on critique
    """
    critique = state.get("critique_results", {})
    recommendation = critique.get("recommendation", "approve")

    # Normalize recommendation
    if recommendation not in ["approve", "revise", "reject"]:
        recommendation = "approve"

    logging.info(f"[Critique Router] → {recommendation}")
    return recommendation  # type: ignore


def grading_router(state: VerificationState) -> Literal["complete", "refine", "new_approach", "max_iterations"]:
    """
    Route based on Grader assessment and termination conditions.

    Flow:
    - complete → END (100% coverage or success criteria met)
    - refine → Refiner (continue improving)
    - new_approach → Generator (stuck, try fresh approach)
    - max_iterations → END (hit iteration limits)

    Args:
        state: Current state

    Returns:
        Routing decision based on grading and limits
    """

    # Check hard limits first
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 50)
    valid_iterations = state.get("valid_iterations", 0)
    max_valid_iter = state.get("max_valid_iter", 20)

    if iteration >= max_iterations:
        logging.info(f"[Grading Router] → max_iterations (iteration {iteration} >= {max_iterations})")
        return "max_iterations"

    if valid_iterations >= max_valid_iter:
        logging.info(f"[Grading Router] → max_iterations (valid_iter {valid_iterations} >= {max_valid_iter})")
        return "max_iterations"

    # Check coverage goal
    sim_results = state.get("simulation_results", {})
    coverage = sim_results.get("coverage", 0.0)

    if coverage >= 100.0:
        logging.info(f"[Grading Router] → complete (100% coverage achieved)")
        return "complete"

    # Check grader recommendation
    grading = state.get("grading_results", {})

    if not grading.get("continue_iteration", True):
        logging.info(f"[Grading Router] → new_approach (grader recommends stop)")
        return "new_approach"

    # Check for plateau (stuck)
    if grading.get("plateau_detected", False):
        logging.info(f"[Grading Router] → new_approach (plateau detected)")
        return "new_approach"

    # Alternative plateau detection based on coverage history
    coverage_history = state.get("coverage_history", [])
    if len(coverage_history) >= 3:
        recent = coverage_history[-3:]
        if max(recent) - min(recent) < 1.0:  # Less than 1% improvement over 3 iterations
            logging.info(f"[Grading Router] → new_approach (coverage plateau: {recent})")
            return "new_approach"

    # Normal refinement
    logging.info(f"[Grading Router] → refine (coverage {coverage:.1f}%, continue improving)")
    return "refine"


def error_router(state: VerificationState) -> Literal["fix_errors", "timeout", "json_error", "simulator"]:
    """
    Route based on error types (optional, for more granular error handling).

    Args:
        state: Current state

    Returns:
        Routing decision based on error type
    """
    sim_results = state.get("simulation_results", {})

    if sim_results.get("success", False):
        return "simulator"

    error_code = sim_results.get("error_code", 0)

    if error_code in [1, 2]:  # Compilation/simulation errors
        logging.info(f"[Error Router] → fix_errors (error_code {error_code})")
        return "fix_errors"
    elif error_code == 3:  # Timeout
        logging.info(f"[Error Router] → timeout")
        return "timeout"
    elif error_code in [4, 5]:  # JSON/format errors
        logging.info(f"[Error Router] → json_error")
        return "json_error"
    else:
        return "simulator"
