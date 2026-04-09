"""Shared result extraction for CovAgent v2 sub-agents.

Both Analyzer-Generator and CRT agents produce the same result format.
This module provides the common extraction logic.
"""

import json
import logging

from ...utils.event_log import emit


def extract_agent_result(
    result: dict,
    gen_id: int,
    iteration: int,
    target_module: str,
    tb_path: str,
    agent_type: str = "generator",
) -> dict:
    """Extract structured results from a sub-agent's final state.

    Scans the agent's message history for the last successful
    run_simulation ToolMessage to extract the coverage_db_path.

    Args:
        result: The agent's invoke() return value (contains "messages").
        gen_id: Unique generator ID.
        iteration: Current iteration.
        target_module: Module being tested.
        tb_path: Expected testbench path.
        agent_type: Agent type for event logging ("analyzer_generator", "crt", "generator").

    Returns:
        Dict with: success, summary, coverage_db_path, testbench_path, gen_id, target_module.
    """
    messages = result.get("messages", [])
    coverage_db_path = None
    success = False
    summary_parts = []

    # Scan for the last successful simulation result
    for msg in reversed(messages):
        if hasattr(msg, 'name') and msg.name == 'run_simulation':
            try:
                content = msg.content
                if isinstance(content, str):
                    parsed = json.loads(content)
                else:
                    parsed = content
                if isinstance(parsed, dict) and parsed.get("success"):
                    coverage_db_path = parsed.get("coverage_db_path")
                    success = True
                    break
            except (json.JSONDecodeError, TypeError):
                continue

    # Extract the agent's final message as summary
    for msg in reversed(messages):
        if type(msg).__name__ == 'AIMessage' and hasattr(msg, 'content') and msg.content:
            summary_parts.append(msg.content[:500])
            break

    if not summary_parts:
        summary_parts.append(f"{agent_type} completed without a final summary message.")

    summary = summary_parts[0]

    gen_result = {
        "success": success,
        "summary": summary,
        "coverage_db_path": coverage_db_path,
        "testbench_path": tb_path if success else None,
        "gen_id": gen_id,
        "target_module": target_module,
    }

    emit(f"{agent_type}_result", {
        "gen_id": gen_id,
        "iteration": iteration,
        "success": success,
        "coverage_db_path": coverage_db_path,
        "summary_preview": summary[:200],
    })

    logging.info(f"{agent_type.replace('_', ' ').title()} {gen_id} result: "
                 f"{'SUCCESS' if success else 'FAILED'}"
                 f"{f' coverage_db={coverage_db_path}' if coverage_db_path else ''}")

    return gen_result
