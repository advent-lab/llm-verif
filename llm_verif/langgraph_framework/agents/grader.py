"""
Grader Agent (NEW)

Post-simulation quality assessment providing rich feedback beyond coverage percentages.
"""

import logging
import json
import re
from typing import Dict, Any
from llm_verif.langgraph_framework.state import VerificationState
from llm_verif.langgraph_framework.prompts.grader_prompts import build_grading_prompt


async def grader_agent(state: VerificationState, llm_backend) -> Dict[str, Any]:
    """
    Agent 4: Grader (NEW)
    Post-simulation quality assessment and learning feedback.

    Provides multi-dimensional evaluation:
    - Coverage achievement
    - Test diversity
    - Coverage strategy quality
    - Improvement trajectory
    - Gap analysis
    - Specific improvement recommendations

    Args:
        state: Current verification state
        llm_backend: LLM backend

    Returns:
        State update with grading_results
    """
    logging.info("[Grader Agent] Grading testbench results...")

    # Skip if grader disabled
    if not state.get("grading_enabled", True):
        logging.info("[Grader Agent] Skipping (disabled)")
        return {
            "grading_results": {
                "overall_grade": "C",
                "continue_iteration": True,
                "reasoning": "Grader disabled"
            }
        }

    sim_results = state.get("simulation_results", {})

    # Log simulation results summary
    coverage = sim_results.get("coverage", 0.0)
    success = sim_results.get("success", False)
    logging.info(f"[Grader Agent] Simulation result: {'SUCCESS' if success else 'FAILED'}, coverage: {coverage:.2f}%")

    # Skip if simulation failed
    if not success:
        logging.info("[Grader Agent] Simulation failed, skipping grading")
        return {
            "grading_results": {
                "overall_grade": "F",
                "quality_score": 0,
                "continue_iteration": True,
                "reasoning": "Simulation failed, needs error fixing"
            }
        }

    # Log context
    iteration = state.get("iteration", 0)
    max_coverage = state.get("max_coverage", 0.0)
    coverage_history = state.get("coverage_history", [])
    logging.info(f"[Grader Agent] Context: iteration {iteration}, max coverage: {max_coverage:.2f}%")
    if len(coverage_history) >= 2:
        recent_improvement = coverage_history[-1] - coverage_history[-2]
        logging.info(f"[Grader Agent] Recent improvement: {recent_improvement:+.2f}%")

    # Build grading prompt
    prompt = build_grading_prompt(
        state["design_spec"],
        state.get("current_testbench", ""),
        sim_results,
        max_coverage,
        coverage_history,
        iteration
    )

    logging.info(f"[Grader Agent] Built grading prompt (length: {len(prompt)} chars)")
    logging.debug(f"[Grader Agent] Prompt preview: {prompt[:300]}...")

    try:
        logging.info("[Grader Agent] Calling LLM for assessment...")

        messages = [
            {"role": "system", "content": "You are a verification quality grading expert analyzing testbench effectiveness."},
            {"role": "user", "content": prompt}
        ]

        if hasattr(llm_backend, 'llm'):
            response = await llm_backend.llm.chat.completions.create(
                model=llm_backend.environment.model_id,
                messages=messages,
                temperature=0.4,  # Slightly higher than critic for some creativity in analysis
                max_tokens=1500
            )
            response_text = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if hasattr(response, 'usage') else 0
            logging.debug(f"[Grader Agent] Response preview: {response_text[:300]}...")
        else:
            response_text = "{}"
            tokens_used = 0
            logging.warning("[Grader Agent] No LLM backend available, using fallback")

        # Parse grading
        grading = _parse_grading_response(response_text)

        # Log parsing success
        if "error" in grading:
            logging.warning(f"[Grader Agent] Response parsing had issues: {grading.get('error', 'Unknown')}")
        else:
            logging.info("[Grader Agent] Successfully parsed grading response")

        grade = grading.get("overall_grade", "C")
        quality = grading.get("quality_score", 50)
        continue_flag = grading.get("continue_iteration", True)
        plateau = grading.get("plateau_detected", False)

        # Log detailed results
        logging.info(
            f"[Grader Agent] Grade: {grade} "
            f"(quality: {quality}/100, continue: {continue_flag}, plateau: {plateau})"
        )

        # Log reasoning
        if "reasoning" in grading:
            logging.info(f"[Grader Agent] Reasoning: {grading['reasoning']}")

        # Log dimension scores if present
        if "dimension_scores" in grading:
            logging.info(f"[Grader Agent] Dimension scores:")
            for dim, score in grading["dimension_scores"].items():
                logging.info(f"[Grader Agent]   - {dim}: {score}")

        # Log specific improvements
        improvements = grading.get("specific_improvements", [])
        if improvements:
            logging.info(f"[Grader Agent] Specific improvements ({len(improvements)}):")
            for i, imp in enumerate(improvements[:3], 1):  # Log first 3
                logging.info(f"[Grader Agent]   {i}. {imp}")
            if len(improvements) > 3:
                logging.info(f"[Grader Agent]   ... and {len(improvements) - 3} more")

        # Log coverage gap analysis
        if "coverage_gap_analysis" in grading:
            logging.info(f"[Grader Agent] Coverage gaps: {grading['coverage_gap_analysis']}")

        # Warn about plateau
        if plateau:
            logging.warning("[Grader Agent] PLATEAU DETECTED - Progress stalled!")

        return {
            "grading_results": grading,
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response_text}
            ],
            "tokens_generated": state.get("tokens_generated", 0) + tokens_used
        }

    except Exception as e:
        logging.error(f"[Grader Agent] Error: {e}")
        # Fallback: continue iteration on error
        return {
            "grading_results": {
                "overall_grade": "C",
                "quality_score": 50,
                "continue_iteration": True,
                "reasoning": f"Grader error: {str(e)}, continuing iteration",
                "error": str(e)
            }
        }


def _parse_grading_response(response: str) -> Dict[str, Any]:
    """
    Parse grading JSON from LLM response.

    Returns:
        Grading dict with grade, scores, analysis, recommendations
    """
    # Try to extract JSON
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if json_match:
        try:
            grading = json.loads(json_match.group(0))

            # Validate required fields
            if "overall_grade" in grading:
                # Ensure continue_iteration is boolean
                if "continue_iteration" not in grading:
                    grading["continue_iteration"] = True
                elif isinstance(grading["continue_iteration"], str):
                    grading["continue_iteration"] = grading["continue_iteration"].lower() == "true"

                # Ensure specific_improvements is a list
                if "specific_improvements" not in grading:
                    grading["specific_improvements"] = []

                # Ensure plateau_detected is boolean
                if "plateau_detected" not in grading:
                    grading["plateau_detected"] = False
                elif isinstance(grading["plateau_detected"], str):
                    grading["plateau_detected"] = grading["plateau_detected"].lower() == "true"

                return grading

        except json.JSONDecodeError as e:
            logging.warning(f"[Grader] JSON parse error: {e}")

    # Fallback: parse as text
    logging.warning("[Grader] Could not parse JSON, using fallback")

    # Try to extract grade
    grade_match = re.search(r'grade[:\s]+([A-F])', response, re.IGNORECASE)
    grade = grade_match.group(1).upper() if grade_match else "C"

    # Try to extract continue decision
    if re.search(r'continue[:\s]+false', response, re.IGNORECASE):
        continue_flag = False
    elif re.search(r'stop|complete|done', response, re.IGNORECASE):
        continue_flag = False
    else:
        continue_flag = True

    # Try to extract plateau detection
    plateau = bool(re.search(r'plateau|stuck|no.*progress', response, re.IGNORECASE))

    return {
        "overall_grade": grade,
        "quality_score": _grade_to_score(grade),
        "continue_iteration": continue_flag,
        "plateau_detected": plateau,
        "reasoning": "Parsed from text response",
        "specific_improvements": [],
        "raw_response": response[:500]
    }


def _grade_to_score(grade: str) -> int:
    """Convert letter grade to numeric score."""
    grade_map = {
        "A": 95,
        "B": 85,
        "C": 75,
        "D": 65,
        "F": 40
    }
    return grade_map.get(grade.upper(), 50)
