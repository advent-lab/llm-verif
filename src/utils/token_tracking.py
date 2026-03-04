"""Token tracking utilities for managing per-API-call token records.

Handles extraction of token usage from LangChain responses, building
standardized token records, and classifying API calls into categories
for analysis.
"""

from typing import Any


def extract_usage_from_response(response) -> dict:
    """Extract token usage details from a LangChain AIMessage response.

    Extracts standard token counts plus reasoning tokens (o-series models)
    and cached input tokens from LangChain's usage_metadata.

    Args:
        response: LangChain AIMessage with usage_metadata attribute.

    Returns:
        Dict with keys: input_tokens, output_tokens, total_tokens,
        reasoning_tokens, cached_input_tokens.
    """
    usage_meta = getattr(response, "usage_metadata", None)

    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    reasoning_tokens = 0
    cached_input_tokens = 0

    if usage_meta:
        input_tokens = usage_meta.get("input_tokens", 0)
        output_tokens = usage_meta.get("output_tokens", 0)
        total_tokens = usage_meta.get("total_tokens", input_tokens + output_tokens)

        output_details = usage_meta.get("output_token_details", {}) or {}
        reasoning_tokens = output_details.get("reasoning", 0) or 0

        input_details = usage_meta.get("input_token_details", {}) or {}
        cached_input_tokens = input_details.get("cache_read", 0) or 0

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "reasoning_tokens": reasoning_tokens,
        "cached_input_tokens": cached_input_tokens,
    }


def build_token_record(
    api_call_num: int,
    iteration: int,
    usage: dict,
    tool_calls: list,
    tool_call_args: list,
    failures: int,
    cumulative_coverage: float,
) -> dict:
    """Build a standardized token usage record for one API call.

    Args:
        api_call_num: Sequential API call number.
        iteration: Current verification iteration.
        usage: Dict from extract_usage_from_response().
        tool_calls: List of tool call names.
        tool_call_args: List of tool call argument dicts.
        failures: Current consecutive failure count.
        cumulative_coverage: Current cumulative coverage percentage.

    Returns:
        Token record dict (category initially "unclassified").
    """
    return {
        "api_call": api_call_num,
        "iteration": iteration,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "reasoning_tokens": usage.get("reasoning_tokens", 0),
        "cached_input_tokens": usage.get("cached_input_tokens", 0),
        "tool_calls": tool_calls,
        "tool_call_args": tool_call_args,
        "failures": failures,
        "cumulative_coverage": cumulative_coverage,
        "category": "unclassified",  # Classified later in update_state_node
    }


def classify_api_call(token_record: dict, state: dict) -> str:
    """Classify an API call into a token usage category based on tool calls and state.

    Categories:
    - new_tb_generation: Writing a new testbench for coverage improvement (not error recovery)
    - spec_rtl_reading: Reading spec/RTL files (outside of error recovery phase)
    - error_recovery: Any action taken while consecutive_failures > 0 (fixing compile/sim errors)
    - overhead: Everything else (compile, simulate, parse_coverage, report writing, reasoning)

    Args:
        token_record: Token record dict for this API call.
        state: Current agent state dict.

    Returns:
        Category string.
    """
    tool_calls = token_record.get("tool_calls", [])
    tool_args = token_record.get("tool_call_args", [])
    failures = token_record.get("failures", 0)
    is_finalizing = state.get("is_finalizing", False)

    # If finalizing (writing report), classify as overhead
    if is_finalizing:
        return "overhead"

    # Error recovery: any call made while failures > 0
    if failures > 0:
        return "error_recovery"

    # Classify based on tool calls
    has_write_file = "write_file" in tool_calls
    has_read_file = "read_file" in tool_calls
    has_compile = "compile_design" in tool_calls
    has_sim = "run_simulation" in tool_calls
    has_coverage = "parse_coverage" in tool_calls
    has_list_dir = "list_directory" in tool_calls

    # Check if write_file targets testbenches/ (new TB generation)
    if has_write_file:
        for i, name in enumerate(tool_calls):
            if name == "write_file" and i < len(tool_args):
                path = tool_args[i].get("path", "")
                if "testbenches/" in path and "report" not in path.lower():
                    return "new_tb_generation"
                elif "report" in path.lower():
                    return "overhead"
        # write_file to non-testbench location
        return "overhead"

    # Read file calls: spec/RTL reading
    if has_read_file and not has_compile and not has_sim and not has_coverage:
        return "spec_rtl_reading"

    # Compile, simulate, coverage analysis, list_dir = overhead
    if has_compile or has_sim or has_coverage or has_list_dir:
        return "overhead"

    # No tool calls (pure reasoning) = overhead
    if not tool_calls:
        return "overhead"

    # Default
    return "overhead"


def classify_pending_records(state: dict) -> None:
    """Classify any unclassified token usage records in state (in-place mutation).

    Args:
        state: Agent state dict containing token_usage list.
    """
    token_usage = state.get("token_usage", [])
    if not token_usage:
        return

    for record in token_usage:
        if record.get("category") == "unclassified":
            record["category"] = classify_api_call(record, state)
