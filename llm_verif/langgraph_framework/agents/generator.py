"""
Generator Agent

Generates SystemVerilog testbenches from specifications and feedback.
"""

import logging
import time
from typing import Dict, Any
from llm_verif.langgraph_framework.state import VerificationState, build_conversation_context
from llm_verif.prompt_templates import (
    system_prompt,
    first_testbench_prompt,
    iter_prompt,
    error_prompt
)
from llm_verif.modelchat import ModelChat


async def generator_agent(state: VerificationState, llm_backend, environment) -> Dict[str, Any]:
    """
    Agent 2: Generator
    Generates SystemVerilog testbenches.

    Args:
        state: Current verification state
        llm_backend: LLM backend
        environment: Environment with design info

    Returns:
        State update with current_testbench, batch_candidates, messages
    """
    iteration = state.get("iteration", 0)
    logging.info(f"[Generator Agent] Generating testbench (iteration {iteration})...")

    # Determine prompt based on iteration and previous results
    prompt = _build_generation_prompt(state, environment)

    # Log prompt type and details
    prompt_type = "first" if iteration == 0 else "iteration" if state.get("simulation_success", True) else "error"
    logging.info(f"[Generator Agent] Using {prompt_type} prompt (length: {len(prompt)} chars)")
    logging.debug(f"[Generator Agent] Prompt preview: {prompt[:300]}...")

    # Build conversation context
    messages = build_conversation_context(state)
    logging.debug(f"[Generator Agent] Built conversation context with {len(messages)} messages")

    # Add system prompt if not present or needs update
    sys_prompt = system_prompt(
        state["design_spec"],
        state["module_header"],
        state.get("design_files", []) if not state.get("no_design_prompt") else None
    )

    if not messages or messages[0]["role"] != "system":
        messages = [{"role": "system", "content": sys_prompt}] + messages

    # Add user prompt
    messages.append({"role": "user", "content": prompt})

    try:
        # Generate with batch support
        batch_size = state.get("batch_size", 1)
        temperature = state.get("temperature", 0.3)

        logging.info(f"[Generator Agent] Calling LLM (batch_size={batch_size}, temp={temperature})...")
        start_time = time.time()

        # Call LLM async
        if hasattr(llm_backend, 'llm'):
            # OpenAI backend
            responses = []
            tokens_total = 0

            for i in range(batch_size):
                response = await llm_backend.llm.chat.completions.create(
                    model=environment.model_id,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=4000
                )
                responses.append(response.choices[0].message.content)
                if hasattr(response, 'usage'):
                    tokens_total += response.usage.total_tokens

            elapsed = time.time() - start_time
            logging.info(f"[Generator Agent] Generated {len(responses)} testbench(es) ({tokens_total} tokens, {elapsed:.2f}s)")
            for i, resp in enumerate(responses[:2], 1):  # Log preview of first 2 responses
                logging.debug(f"[Generator Agent] Response {i} preview: {resp[:200]}...")

        else:
            # Fallback
            responses = [""]
            tokens_total = 0
            elapsed = 0
            logging.warning("[Generator Agent] No LLM backend available, using fallback")

        # Parse testbenches
        testbenches = []
        for resp in responses:
            parsed = ModelChat.convert_json_response_to_dict(resp)
            if parsed[1] == 0:  # Success
                testbenches.append({
                    "code": parsed[0].get("test bench", ""),
                    "comments": parsed[0].get("comments", "")
                })
            else:
                # JSON parse failed
                testbenches.append({
                    "code": "",
                    "comments": f"JSON parse error: {parsed[0].get('error', 'Unknown')}"
                })

        # Filter successful testbenches
        successful_testbenches = [tb for tb in testbenches if tb["code"]]

        # Log parsing results
        logging.info(f"[Generator Agent] Parsing: {len(successful_testbenches)}/{len(testbenches)} successful")
        for i, tb in enumerate(testbenches):
            if tb["code"]:
                logging.debug(f"[Generator Agent] Testbench {i+1}: {len(tb['code'])} chars, comments: {tb['comments'][:100]}...")
            else:
                logging.warning(f"[Generator Agent] Testbench {i+1} FAILED: {tb['comments']}")

        if not successful_testbenches:
            logging.error("[Generator Agent] No successful testbenches generated!")
            return {
                "current_testbench": "",
                "current_testbench_comments": "Failed to generate valid testbench",
                "batch_candidates": [],
                "generation_count": state.get("generation_count", 0) + 1,
                "tokens_generated": tokens_total,
                "total_generation_time": state.get("total_generation_time", 0) + elapsed
            }

        # Select first successful as current
        current_tb = successful_testbenches[0]

        # Log testbench stats
        code_length = len(current_tb["code"])
        line_count = current_tb["code"].count('\n')
        logging.info(f"[Generator Agent] Selected testbench: {line_count} lines, {code_length} chars")
        logging.info(f"[Generator Agent] Generated {len(successful_testbenches)}/{len(testbenches)} valid testbenches")
        if current_tb["comments"]:
            logging.info(f"[Generator Agent] Comments: {current_tb['comments'][:150]}...")

        return {
            "current_testbench": current_tb["code"],
            "current_testbench_comments": current_tb["comments"],
            "batch_candidates": [tb["code"] for tb in successful_testbenches],
            "generated_testbenches": [
                {
                    "code": tb["code"],
                    "iteration": iteration,
                    "source": "initial" if iteration == 0 else "refined"
                }
                for tb in successful_testbenches
            ],
            "generation_count": state.get("generation_count", 0) + 1,
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": responses[0]}
            ],
            "tokens_generated": tokens_total,
            "total_generation_time": state.get("total_generation_time", 0) + elapsed
        }

    except Exception as e:
        logging.error(f"[Generator Agent] Error: {e}")
        return {
            "current_testbench": "",
            "current_testbench_comments": f"Generation error: {str(e)}",
            "batch_candidates": [],
            "generation_count": state.get("generation_count", 0) + 1
        }


def _build_generation_prompt(state: VerificationState, environment) -> str:
    """
    Build appropriate generation prompt based on state.

    Args:
        state: Current state
        environment: Environment

    Returns:
        Prompt string
    """
    iteration = state.get("iteration", 0)
    sim_results = state.get("simulation_results", {})

    # First iteration: initial testbench
    if iteration == 0:
        return first_testbench_prompt(
            state["design_spec"],
            state["module_header"]
        )

    # Check if previous simulation failed
    if not state.get("simulation_success", True):
        error_code = sim_results.get("error_code", 0)
        error_message = sim_results.get("error_message", "Unknown error")
        return error_prompt(error_code, error_message)

    # Normal iteration: coverage improvement
    # Build a CoverageResponse-like object for iter_prompt
    from llm_verif.simulator import CoverageResponse

    cov = CoverageResponse(
        success=sim_results.get("success", False),
        error_code=sim_results.get("error_code", 0),
        error_message=sim_results.get("error_message", ""),
        coverage_list=sim_results.get("coverage_list", []),
        total_coverage=sim_results.get("coverage", 0.0)
    )

    # Use existing iter_prompt from prompt_templates
    return iter_prompt(
        cov,
        state.get("design_module_name", ""),
        None,  # simulator (will use cov data)
        state.get("work_dir", "")
    )
