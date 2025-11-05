"""
Planner Agent

Generates high-level verification strategy and test plan before testbench generation.
"""

import logging
import json
import re
from typing import Dict, Any
from llm_verif.langgraph_framework.state import VerificationState
from llm_verif.prompt_templates import verification_plan_prompt, system_prompt


async def planner_agent(state: VerificationState, llm_backend) -> Dict[str, Any]:
    """
    Agent 1: Planner
    Generates verification plan with objectives and scenarios.

    Args:
        state: Current verification state
        llm_backend: LLM backend (OpenAIBackend or LlamaChat)

    Returns:
        State update dict with verification_plan and plan_available
    """
    logging.info("[Planner Agent] Starting verification planning...")

    # Skip if planning disabled or plan already exists
    if not state.get("testplan_enabled", False) or state.get("plan_available", False):
        logging.info(f"[Planner Agent] Skipping (testplan_enabled={state.get('testplan_enabled')}, plan_available={state.get('plan_available')})")
        return {
            "plan_available": True,
            "verification_plan": state.get("verification_plan", {})
        }

    # Build system prompt
    sys_prompt = system_prompt(
        state["design_spec"],
        state["module_header"],
        state.get("design_files", [])
    )

    # Build planning prompt
    plan_prompt = verification_plan_prompt()

    # Log prompt details
    logging.info(f"[Planner Agent] Built planning prompt (length: {len(plan_prompt)} chars)")
    logging.debug(f"[Planner Agent] System prompt preview: {sys_prompt[:200]}...")
    logging.debug(f"[Planner Agent] Planning prompt preview: {plan_prompt[:200]}...")

    try:
        # Call LLM
        logging.info("[Planner Agent] Calling LLM for verification plan...")

        # Build messages
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": plan_prompt}
        ]

        # Call LLM (async)
        if hasattr(llm_backend, 'generate_response_async'):
            # For OpenAI backend
            response = await llm_backend.llm.chat.completions.create(
                model=llm_backend.environment.model_id,
                messages=messages,
                temperature=0.7,
                max_tokens=2000
            )
            response_text = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if hasattr(response, 'usage') else 0
        else:
            # Fallback for non-async
            response_text = "Planning not available"
            tokens_used = 0

        logging.info(f"[Planner Agent] Received response ({tokens_used} tokens)")
        logging.debug(f"[Planner Agent] Response preview: {response_text[:300]}...")

        # Parse plan (extract JSON or use full text)
        plan = _parse_plan_response(response_text)

        # Log parsed plan details
        objectives = plan.get('objectives', [])
        scenarios = plan.get('scenarios', [])
        logging.info(f"[Planner Agent] Plan generated with {len(objectives)} objectives and {len(scenarios)} scenarios")
        if objectives:
            logging.info(f"[Planner Agent] Objectives:")
            for i, obj in enumerate(objectives[:3], 1):  # Log first 3
                logging.info(f"[Planner Agent]   {i}. {obj}")
            if len(objectives) > 3:
                logging.info(f"[Planner Agent]   ... and {len(objectives) - 3} more")
        if scenarios:
            logging.info(f"[Planner Agent] Test scenarios:")
            for i, scen in enumerate(scenarios[:3], 1):  # Log first 3
                logging.info(f"[Planner Agent]   {i}. {scen}")
            if len(scenarios) > 3:
                logging.info(f"[Planner Agent]   ... and {len(scenarios) - 3} more")

        return {
            "verification_plan": plan,
            "plan_available": True,
            "messages": [
                {"role": "user", "content": plan_prompt},
                {"role": "assistant", "content": response_text}
            ],
            "tokens_generated": tokens_used
        }

    except Exception as e:
        logging.error(f"[Planner Agent] Error: {e}")
        # Fallback to empty plan
        return {
            "verification_plan": {
                "objectives": ["Achieve 100% statement coverage"],
                "scenarios": ["Random stimulus generation"],
                "error": str(e)
            },
            "plan_available": True
        }


def _parse_plan_response(response: str) -> Dict[str, Any]:
    """
    Parse verification plan from LLM response.

    Tries to extract JSON if present, otherwise parses as structured text.
    """
    # Try JSON extraction
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    # Parse as structured text
    plan = {
        "objectives": [],
        "scenarios": [],
        "raw_text": response
    }

    # Extract objectives (look for bullet points or numbered lists)
    obj_section = re.search(r'(?:objectives?|goals?):?(.*?)(?:\n\n|\Z)', response, re.IGNORECASE | re.DOTALL)
    if obj_section:
        objectives_text = obj_section.group(1)
        # Extract bullet points or numbered items
        objectives = re.findall(r'(?:^|\n)\s*(?:[-*•]|\d+\.)\s*(.+)', objectives_text)
        plan["objectives"] = [obj.strip() for obj in objectives if obj.strip()]

    # Extract scenarios
    scen_section = re.search(r'(?:scenarios?|test cases?):?(.*?)(?:\n\n|\Z)', response, re.IGNORECASE | re.DOTALL)
    if scen_section:
        scenarios_text = scen_section.group(1)
        scenarios = re.findall(r'(?:^|\n)\s*(?:[-*•]|\d+\.)\s*(.+)', scenarios_text)
        plan["scenarios"] = [scen.strip() for scen in scenarios if scen.strip()]

    return plan
