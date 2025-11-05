"""
Refiner Agent

Synthesizes feedback from multiple agents (Critic, Grader, Simulator) to make
targeted improvements to the testbench.
"""

import logging
import time
from typing import Dict, Any
from llm_verif.langgraph_framework.state import VerificationState, build_conversation_context
from llm_verif.langgraph_framework.prompts.refiner_prompts import build_refinement_prompt
from llm_verif.prompt_templates import system_prompt
from llm_verif.modelchat import ModelChat


async def refiner_agent(state: VerificationState, llm_backend, environment) -> Dict[str, Any]:
    """
    Agent 5: Refiner
    Targeted improvements based on multi-agent feedback.

    Synthesizes feedback from:
    - Critic: pre-simulation quality issues
    - Grader: post-simulation assessment
    - Simulator: coverage gaps and errors

    Args:
        state: Current verification state
        llm_backend: LLM backend
        environment: Environment

    Returns:
        State update with refined current_testbench
    """
    iteration = state.get("iteration", 0)
    logging.info(f"[Refiner Agent] Refining testbench (iteration {iteration})...")

    # Gather all feedback
    critique = state.get("critique_results")
    grading = state.get("grading_results")
    sim_results = state.get("simulation_results")

    # Log available feedback
    has_critique = critique is not None
    has_grading = grading is not None
    has_sim = sim_results is not None
    logging.info(f"[Refiner Agent] Available feedback: critique={'✓' if has_critique else '✗'}, grading={'✓' if has_grading else '✗'}, sim={'✓' if has_sim else '✗'}")

    # Log feedback summaries
    if critique:
        critique_rec = critique.get("recommendation", "unknown")
        critique_score = critique.get("critique_score", 0)
        logging.info(f"[Refiner Agent] Critic: {critique_rec} (score: {critique_score}/100)")

    if grading:
        grade = grading.get("overall_grade", "?")
        quality = grading.get("quality_score", 0)
        logging.info(f"[Refiner Agent] Grader: {grade} (quality: {quality}/100)")

    if sim_results:
        sim_success = sim_results.get("success", False)
        sim_coverage = sim_results.get("coverage", 0.0)
        logging.info(f"[Refiner Agent] Simulation: {'SUCCESS' if sim_success else 'FAILED'} (coverage: {sim_coverage:.2f}%)")

    # Determine refinement priority
    priority = _determine_refinement_priority(critique, grading, sim_results)
    logging.info(f"[Refiner Agent] Refinement priority: {priority}")

    # Build comprehensive refinement prompt
    prompt = build_refinement_prompt(
        current_testbench=state.get("current_testbench", ""),
        design_spec=state["design_spec"],
        module_header=state["module_header"],
        critique=critique,
        grading=grading,
        sim_results=sim_results
    )

    # Build conversation context
    messages = build_conversation_context(state)

    # Add/update system prompt
    sys_prompt = system_prompt(
        state["design_spec"],
        state["module_header"],
        state.get("design_files", []) if not state.get("no_design_prompt") else None
    )

    if not messages or messages[0]["role"] != "system":
        messages = [{"role": "system", "content": sys_prompt}] + messages
    else:
        messages[0] = {"role": "system", "content": sys_prompt}

    # Add refinement prompt
    messages.append({"role": "user", "content": prompt})

    logging.info(f"[Refiner Agent] Built refinement prompt (length: {len(prompt)} chars)")
    logging.debug(f"[Refiner Agent] Prompt preview: {prompt[:300]}...")
    logging.debug(f"[Refiner Agent] Conversation context: {len(messages)} messages")

    try:
        # Adaptive temperature based on progress
        temperature = _get_adaptive_temperature(state)
        base_temp = state.get("temperature", 0.7)

        if temperature != base_temp:
            logging.info(f"[Refiner Agent] Adaptive temperature: {temperature:.2f} (base: {base_temp:.2f})")
        else:
            logging.info(f"[Refiner Agent] Using base temperature: {temperature:.2f}")

        logging.info(f"[Refiner Agent] Calling LLM (temp={temperature:.2f})...")
        start_time = time.time()

        # Call LLM
        if hasattr(llm_backend, 'llm'):
            response = await llm_backend.llm.chat.completions.create(
                model=llm_backend.environment.model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=4000
            )
            response_text = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if hasattr(response, 'usage') else 0
            logging.debug(f"[Refiner Agent] Response preview: {response_text[:300]}...")
        else:
            response_text = "{}"
            tokens_used = 0
            logging.warning("[Refiner Agent] No LLM backend available, using fallback")

        elapsed = time.time() - start_time
        logging.info(f"[Refiner Agent] LLM response received ({tokens_used} tokens, {elapsed:.2f}s)")

        # Parse refined testbench
        parsed, status = ModelChat.convert_json_response_to_dict(response_text)

        # Log parsing result
        if status == 0:
            logging.info("[Refiner Agent] Successfully parsed JSON response")
        else:
            logging.error(f"[Refiner Agent] JSON parsing FAILED (status: {status})")

        if status == 0:  # Success
            testbench_code = parsed.get("test bench", "")
            comments = parsed.get("comments", "")
            strategy = parsed.get("refinement_strategy", "optimize")

            # Log testbench stats
            if testbench_code:
                code_lines = testbench_code.count('\n')
                code_length = len(testbench_code)
                logging.info(f"[Refiner Agent] Refined testbench: {code_lines} lines, {code_length} chars")
            else:
                logging.warning("[Refiner Agent] No testbench code in response!")

            logging.info(f"[Refiner Agent] Refinement complete: {strategy} strategy")
            if comments:
                logging.info(f"[Refiner Agent] Comments: {comments[:150]}...")

            return {
                "current_testbench": testbench_code,
                "current_testbench_comments": comments,
                "iteration": iteration + 1,
                "messages": [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": response_text}
                ],
                "tokens_generated": state.get("tokens_generated", 0) + tokens_used,
                "total_generation_time": state.get("total_generation_time", 0) + elapsed,
                "temperature": temperature
            }
        else:
            # JSON parse error
            error_msg = parsed.get('error', 'Unknown')
            logging.error(f"[Refiner Agent] JSON parse error: {error_msg}")
            logging.debug(f"[Refiner Agent] Raw response that failed to parse: {response_text[:500]}...")
            return {
                "iteration": iteration + 1,
                "tokens_generated": state.get("tokens_generated", 0) + tokens_used
            }

    except Exception as e:
        logging.error(f"[Refiner Agent] Error: {e}", exc_info=True)
        return {
            "iteration": iteration + 1
        }


def _get_adaptive_temperature(state: VerificationState) -> float:
    """
    Calculate adaptive temperature based on progress.

    Higher temperature when stuck (need creativity).
    Lower temperature when making progress (be consistent).

    Args:
        state: Current state

    Returns:
        Temperature value (0.0-1.0)
    """
    coverage_history = state.get("coverage_history", [])

    # Default temperature
    base_temp = state.get("temperature", 0.7)

    if len(coverage_history) < 2:
        return base_temp

    # Check recent improvement
    recent_improvement = coverage_history[-1] - coverage_history[-2]

    if recent_improvement > 5.0:
        # Making good progress, be more consistent
        return max(0.5, base_temp - 0.1)
    elif recent_improvement < 1.0:
        # Slow progress, try more creativity
        return min(0.9, base_temp + 0.2)
    else:
        # Normal progress
        return base_temp


def _determine_refinement_priority(
    critique: Dict[str, Any],
    grading: Dict[str, Any],
    sim_results: Dict[str, Any]
) -> str:
    """
    Determine refinement priority based on feedback.

    Returns:
        Priority string: "errors", "coverage", "plateau", "optimize"
    """
    # Priority 1: Fix errors
    if critique:
        critical_issues = [
            issue for issue in critique.get("issues", [])
            if issue.get("severity") == "critical"
        ]
        if critical_issues:
            return "errors"

    if sim_results and not sim_results.get("success"):
        return "errors"

    # Priority 2: Break plateau
    if grading and grading.get("plateau_detected"):
        return "plateau"

    # Priority 3: Coverage improvement
    if sim_results and sim_results.get("coverage", 0) < 100:
        return "coverage"

    # Priority 4: Optimization
    return "optimize"
