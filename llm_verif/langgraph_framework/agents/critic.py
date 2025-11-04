"""
Critic Agent (NEW)

Pre-simulation quality assessment to catch errors before expensive simulation runs.
This is a key innovation that reduces wasted simulator calls.
"""

import logging
import json
import re
from typing import Dict, Any
from llm_verif.langgraph_framework.state import VerificationState
from llm_verif.langgraph_framework.prompts.critic_prompts import build_critique_prompt


async def critic_agent(state: VerificationState, llm_backend) -> Dict[str, Any]:
    """
    Agent 3: Critic (NEW)
    Pre-simulation quality check and code review.

    This agent catches obvious errors BEFORE running expensive simulations:
    - Missing $finish (causes timeout)
    - Syntax errors
    - Missing clock/reset
    - Infinite loops

    Args:
        state: Current verification state
        llm_backend: LLM backend

    Returns:
        State update with critique_results
    """
    logging.info("[Critic Agent] Reviewing testbench quality...")

    # Skip if critic disabled
    if not state.get("critique_enabled", True):
        logging.info("[Critic Agent] Skipping (disabled)")
        return {
            "critique_results": {
                "recommendation": "approve",
                "critique_score": 100,
                "issues": [],
                "reasoning": "Critic disabled"
            }
        }

    code = state.get("current_testbench", "")
    if not code:
        logging.warning("[Critic Agent] No testbench to review!")
        return {
            "critique_results": {
                "recommendation": "reject",
                "critique_score": 0,
                "issues": [{"severity": "critical", "description": "Empty testbench", "suggestion": "Generate testbench"}],
                "reasoning": "No code to review"
            }
        }

    # Build critique prompt
    prompt = build_critique_prompt(
        state["design_spec"],
        code,
        state.get("verification_plan", {})
    )

    try:
        logging.info("[Critic Agent] Calling LLM for code review...")

        # Call LLM with lower temperature (analytical task)
        messages = [
            {"role": "system", "content": "You are an expert SystemVerilog verification engineer performing code review."},
            {"role": "user", "content": prompt}
        ]

        if hasattr(llm_backend, 'llm'):
            response = await llm_backend.llm.chat.completions.create(
                model=llm_backend.environment.model_id,
                messages=messages,
                temperature=0.3,  # Lower temperature for precise analysis
                max_tokens=1000
            )
            response_text = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if hasattr(response, 'usage') else 0
        else:
            response_text = "{}"
            tokens_used = 0

        # Parse critique
        critique = _parse_critique_response(response_text)

        score = critique.get("critique_score", 50)
        recommendation = critique.get("recommendation", "approve")
        issues_count = len(critique.get("issues", []))
        critical_count = sum(1 for issue in critique.get("issues", []) if issue.get("severity") == "critical")

        logging.info(
            f"[Critic Agent] Review complete: {recommendation.upper()} "
            f"(score: {score}/100, {issues_count} issues, {critical_count} critical)"
        )

        # Update metrics
        critic_rejections = state.get("critic_rejections", 0)
        if recommendation == "reject":
            critic_rejections += 1

        return {
            "critique_results": critique,
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response_text}
            ],
            "tokens_generated": state.get("tokens_generated", 0) + tokens_used,
            "critic_rejections": critic_rejections
        }

    except Exception as e:
        logging.error(f"[Critic Agent] Error: {e}")
        # Fallback: approve on error (don't block workflow)
        return {
            "critique_results": {
                "recommendation": "approve",
                "critique_score": 50,
                "issues": [],
                "reasoning": f"Critic error: {str(e)}, proceeding to simulation",
                "error": str(e)
            }
        }


def _parse_critique_response(response: str) -> Dict[str, Any]:
    """
    Parse critique JSON from LLM response.

    Returns:
        Critique dict with score, issues, recommendation, reasoning
    """
    # Try to extract JSON
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if json_match:
        try:
            critique = json.loads(json_match.group(0))

            # Validate required fields
            if "critique_score" in critique and "recommendation" in critique:
                # Ensure issues is a list
                if "issues" not in critique:
                    critique["issues"] = []

                # Normalize recommendation
                rec = critique["recommendation"].lower()
                if rec not in ["approve", "revise", "reject"]:
                    # Default to approve if invalid
                    critique["recommendation"] = "approve"
                else:
                    critique["recommendation"] = rec

                return critique

        except json.JSONDecodeError as e:
            logging.warning(f"[Critic] JSON parse error: {e}")

    # Fallback: parse as text
    logging.warning("[Critic] Could not parse JSON, using fallback")

    # Try to extract score
    score_match = re.search(r'score[:\s]+(\d+)', response, re.IGNORECASE)
    score = int(score_match.group(1)) if score_match else 70

    # Try to extract recommendation
    if re.search(r'\breject\b', response, re.IGNORECASE):
        recommendation = "reject"
    elif re.search(r'\brevise\b', response, re.IGNORECASE):
        recommendation = "revise"
    else:
        recommendation = "approve"

    return {
        "critique_score": score,
        "recommendation": recommendation,
        "issues": [],
        "reasoning": "Parsed from text response",
        "raw_response": response[:500]
    }
