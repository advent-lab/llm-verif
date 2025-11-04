#!/usr/bin/env python3
"""
Comparison Script: Original vs LangGraph Implementation

Run the same design through both systems and compare results.

Usage:
    python scripts/compare_langgraph.py --design designs/counter --simulator verilator
"""

import asyncio
import argparse
import subprocess
import json
import pandas as pd
from pathlib import Path


def run_original(design, simulator, max_iterations=10):
    """Run original llm_verif.py implementation."""
    print(f"\n{'='*80}")
    print(f"RUNNING ORIGINAL SYSTEM")
    print(f"{'='*80}\n")

    cmd = [
        "python", "llm_verif.py",
        "--design", design,
        "--compiler", "iverilog",
        "--id", "original_test",
        "--simulator", simulator,
        "--backend", "openai",
        "--max_iterations", str(max_iterations),
        "--runs", "1"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)

    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")

    return result.returncode == 0


async def run_langgraph(design, simulator, max_iterations=10):
    """Run new llm_verif_langgraph.py implementation."""
    print(f"\n{'='*80}")
    print(f"RUNNING LANGGRAPH SYSTEM")
    print(f"{'='*80}\n")

    cmd = [
        "python", "llm_verif_langgraph.py",
        "--design", design,
        "--compiler", "iverilog",
        "--id", "langgraph_test",
        "--simulator", simulator,
        "--backend", "openai",
        "--max_iterations", str(max_iterations),
        "--runs", "1",
        "--enable_critic",
        "--enable_grader"
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await proc.communicate()

    print(stdout.decode())

    if proc.returncode != 0:
        print(f"ERROR: {stderr.decode()}")

    return proc.returncode == 0


def compare_results(design_name):
    """Compare CSV results from both runs."""
    print(f"\n{'='*80}")
    print(f"COMPARING RESULTS")
    print(f"{'='*80}\n")

    # Find CSV files
    csv_dir = Path(".")
    original_csv = list(csv_dir.glob(f"*{design_name}*original_test*.csv"))
    langgraph_csv = list(csv_dir.glob(f"*{design_name}*langgraph_test*.csv"))

    if not original_csv or not langgraph_csv:
        print("WARNING: Could not find CSV files for comparison")
        return

    # Load CSVs
    df_orig = pd.read_csv(original_csv[0])
    df_lang = pd.read_csv(langgraph_csv[0])

    # Compare metrics
    comparison = {
        "Metric": [
            "Max Coverage (%)",
            "Iterations",
            "Valid Iterations",
            "Avg Tokens/Iteration",
            "Total Time (s)"
        ],
        "Original": [
            df_orig["max_coverage"].max(),
            df_orig["iteration"].max(),
            df_orig[df_orig["pass_fail"] == True]["iteration"].count(),
            df_orig["tokens_generated"].mean(),
            df_orig["generation_time"].sum()
        ],
        "LangGraph": [
            df_lang["max_coverage"].max() if "max_coverage" in df_lang.columns else "N/A",
            df_lang["iteration"].max() if "iteration" in df_lang.columns else "N/A",
            df_lang[df_lang["pass_fail"] == True]["iteration"].count() if "pass_fail" in df_lang.columns else "N/A",
            df_lang["tokens_generated"].mean() if "tokens_generated" in df_lang.columns else "N/A",
            df_lang["generation_time"].sum() if "generation_time" in df_lang.columns else "N/A"
        ]
    }

    df_comparison = pd.DataFrame(comparison)
    print(df_comparison.to_string(index=False))

    print(f"\nOriginal CSV: {original_csv[0]}")
    print(f"LangGraph CSV: {langgraph_csv[0]}")


async def main():
    parser = argparse.ArgumentParser(description="Compare Original vs LangGraph implementations")
    parser.add_argument("--design", required=True, help="Design directory")
    parser.add_argument("--simulator", required=True, choices=["questasim", "verilator"])
    parser.add_argument("--max_iterations", type=int, default=10, help="Max iterations for test")
    parser.add_argument("--skip_original", action="store_true", help="Skip original run")
    parser.add_argument("--skip_langgraph", action="store_true", help="Skip LangGraph run")

    args = parser.parse_args()

    design_name = Path(args.design).name

    # Run original
    if not args.skip_original:
        success = run_original(args.design, args.simulator, args.max_iterations)
        if not success:
            print("\nWARNING: Original system failed!")

    # Run LangGraph
    if not args.skip_langgraph:
        success = await run_langgraph(args.design, args.simulator, args.max_iterations)
        if not success:
            print("\nWARNING: LangGraph system failed!")

    # Compare results
    if not args.skip_original and not args.skip_langgraph:
        compare_results(design_name)


if __name__ == "__main__":
    asyncio.run(main())
