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

    try:
        # Adaptive temperature based on progress
        temperature = _get_adaptive_temperature(state)

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
        else:
            response_text = "{}"
            tokens_used = 0

        elapsed = time.time() - start_time

        # Parse refined testbench
        parsed, status = ModelChat.convert_json_response_to_dict(response_text)

        if status == 0:  # Success
            testbench_code = parsed.get("test bench", "")
            comments = parsed.get("comments", "")
            strategy = parsed.get("refinement_strategy", "optimize")

            logging.info(f"[Refiner Agent] Refinement complete: {strategy} ({tokens_used} tokens, {elapsed:.2f}s)")

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
            logging.error(f"[Refiner Agent] JSON parse error: {parsed.get('error', 'Unknown')}")
            return {
                "iteration": iteration + 1,
                "tokens_generated": state.get("tokens_generated", 0) + tokens_used
            }

    except Exception as e:
        logging.error(f"[Refiner Agent] Error: {e}")
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
