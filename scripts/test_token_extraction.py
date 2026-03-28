#!/usr/bin/env python3
"""Standalone test script: make one LLM API call via LangChain ChatOpenAI
(the same path used in the framework) and display both the raw response
metadata and the extracted token usage from our token_tracking utilities.

Usage:
    python scripts/test_token_extraction.py                  # uses MODEL from .env or defaults to gpt-4o
    python scripts/test_token_extraction.py --model o3-mini  # override model
"""

import sys
import os
import argparse
import json
from pathlib import Path

# Add project root to path so we can import src.utils
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.utils.token_tracking import extract_usage_from_response, build_token_record


def main():
    parser = argparse.ArgumentParser(description="Test token extraction from a single API call")
    parser.add_argument("--model", type=str, default=None,
                        help="Model to use (default: MODEL from .env or gpt-4o)")
    parser.add_argument("--prompt", type=str,
                        default="Think and write a poem on SystemVerilog",
                        help="User prompt to send")
    args = parser.parse_args()

    # Load .env from project root
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set. Set it in .env or as an environment variable.")
        sys.exit(1)

    model = args.model or os.getenv("MODEL", "gpt-4o")

    print(f"{'='*70}")
    print(f"Token Extraction Test")
    print(f"{'='*70}")
    print(f"Model:  {model}")
    print(f"Prompt: {args.prompt}")
    print(f"{'='*70}\n")

    # --- Build messages (same pattern as agent_node in react.py) ---
    messages = [
        SystemMessage(content="You are a hardworking assistant."),
        HumanMessage(content=args.prompt),
    ]

    # --- Create LLM (same as framework) ---
    llm = ChatOpenAI(
        model=model,
        reasoning_effort="high",
        temperature=0.4,
        max_tokens=4096,
        api_key=api_key,
    )

    # --- Invoke (same as framework: llm_with_tools.invoke, but no tools needed for this test) ---
    print("Sending API request...")
    response = llm.invoke(messages)
    print("Response received.\n")

    # ===================================================================
    # 1. Raw response metadata (what LangChain gives us)
    # ===================================================================
    print(f"{'='*70}")
    print("1. RAW RESPONSE METADATA")
    print(f"{'='*70}")

    print(f"\n  response type: {type(response).__name__}")
    print(f"  response.content: {response.content[:200]}{'...' if len(response.content) > 200 else ''}")

    # usage_metadata
    usage_meta = getattr(response, "usage_metadata", None)
    print(f"\n  response.usage_metadata:")
    if usage_meta:
        print(f"    {json.dumps(dict(usage_meta), indent=4, default=str)}")
    else:
        print(f"    None")

    # response_metadata (contains the raw OpenAI token_usage dict)
    resp_meta = getattr(response, "response_metadata", None)
    print(f"\n  response.response_metadata:")
    if resp_meta:
        # Print token_usage specifically
        token_usage_raw = resp_meta.get("token_usage", {})
        print(f"    token_usage: {json.dumps(token_usage_raw, indent=4, default=str)}")
        print(f"    model_name: {resp_meta.get('model_name', 'N/A')}")
        print(f"    finish_reason: {resp_meta.get('finish_reason', 'N/A')}")
    else:
        print(f"    None")

    # ===================================================================
    # 2. Extracted usage via our token_tracking utility
    # ===================================================================
    print(f"\n{'='*70}")
    print("2. EXTRACTED USAGE (via extract_usage_from_response)")
    print(f"{'='*70}")

    usage = extract_usage_from_response(response)
    for key, value in usage.items():
        print(f"    {key:<25} {value:>10,}")

    # ===================================================================
    # 3. Built token record (same as framework stores in state)
    # ===================================================================
    print(f"\n{'='*70}")
    print("3. TOKEN RECORD (via build_token_record)")
    print(f"{'='*70}")

    record = build_token_record(
        api_call_num=1,
        iteration=1,
        usage=usage,
        tool_calls=[],
        tool_call_args=[],
        failures=0,
        cumulative_coverage=0.0,
    )
    print(f"    {json.dumps(record, indent=4, default=str)}")

    # ===================================================================
    # 4. Verification summary
    # ===================================================================
    print(f"\n{'='*70}")
    print("4. VERIFICATION")
    print(f"{'='*70}")

    issues = []

    # Check that basic tokens are non-zero
    if usage["input_tokens"] == 0:
        issues.append("input_tokens is 0 (expected > 0)")
    if usage["output_tokens"] == 0:
        issues.append("output_tokens is 0 (expected > 0)")
    if usage["total_tokens"] == 0:
        issues.append("total_tokens is 0 (expected > 0)")

    # Check total = input + output (may not hold if reasoning tokens exist)
    expected_total = usage["input_tokens"] + usage["output_tokens"]
    if usage["total_tokens"] != expected_total:
        print(f"    NOTE: total_tokens ({usage['total_tokens']:,}) != input + output ({expected_total:,})")
        print(f"          This is expected if the API counts reasoning tokens differently.")

    # Check reasoning tokens (only expected for o-series models)
    is_reasoning_model = any(tag in model.lower() for tag in ["o1", "o3", "o4"])
    if is_reasoning_model and usage["reasoning_tokens"] == 0:
        issues.append(f"reasoning_tokens is 0 for reasoning model '{model}' (may indicate extraction issue)")
    elif not is_reasoning_model and usage["reasoning_tokens"] > 0:
        print(f"    NOTE: reasoning_tokens > 0 for non-reasoning model '{model}' (unexpected but not an error)")

    if usage["reasoning_tokens"] > 0:
        print(f"    Reasoning tokens: {usage['reasoning_tokens']:,} "
              f"({usage['reasoning_tokens']/usage['output_tokens']*100:.1f}% of output)")

    if usage["cached_input_tokens"] > 0:
        print(f"    Cached input tokens: {usage['cached_input_tokens']:,} "
              f"({usage['cached_input_tokens']/usage['input_tokens']*100:.1f}% of input)")

    if issues:
        print(f"\n    ISSUES FOUND:")
        for issue in issues:
            print(f"      - {issue}")
    else:
        print(f"\n    All checks passed.")

    print()


if __name__ == "__main__":
    main()
