#!/usr/bin/env python3
"""
Token Usage Analyzer — Post-hoc analysis of agent run.log files.

Parses run.log files from work/ReAct/ design directories, classifies each
API call into token usage categories, computes marginal token costs, and
outputs per-design JSON reports plus a summary table.

Categories:
  - new_tb_generation : Writing a new testbench (failures == 0, write_file to testbenches/)
  - spec_rtl_reading  : Reading spec/RTL files (read_file, not during error recovery)
  - error_recovery    : Any API call while failures > 0 (compile/sim error → fix)
  - overhead          : Compile, simulate, coverage analysis, report writing, reasoning

Usage:
    python scripts/analyze_tokens.py --all
    python scripts/analyze_tokens.py --design sha1_top
    python scripts/analyze_tokens.py --design sha1_top chacha_top
    python scripts/analyze_tokens.py --all --output-dir results/
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class APICallRecord:
    """Parsed data for a single API call (REQUEST → RESPONSE pair)."""
    api_call: int = 0
    iteration: int = 1
    cumulative_coverage: float = 0.0
    current_coverage: float = 0.0
    failures: int = 0
    no_progress: int = 0

    # Tiktoken estimate from API REQUEST header (pre-call, ~approximate)
    request_tokens: int = 0

    # Marginal token cost: delta added by this call (request_tokens[N+1] - request_tokens[N])
    marginal_tokens: int = 0

    # API-reported token usage (from AGENT RESPONSE header)
    api_input_tokens: int = 0
    api_output_tokens: int = 0
    api_total_tokens: int = 0
    api_reasoning_tokens: int = 0
    api_cached_input_tokens: int = 0

    # Tool calls made in the RESPONSE
    tool_calls: List[str] = field(default_factory=list)
    tool_args: List[Dict[str, Any]] = field(default_factory=list)

    # Classification
    category: str = "unclassified"

    # Timestamps
    request_time: Optional[str] = None
    response_time: Optional[str] = None


@dataclass
class DesignAnalysis:
    """Aggregated token analysis for a single design."""
    design: str = ""
    model: str = "unknown"
    total_api_calls: int = 0
    total_prompt_tokens_est: int = 0
    total_marginal_tokens: int = 0
    final_coverage: float = 0.0
    run_complete: bool = True  # False if log appears truncated

    categories: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    per_call: List[Dict[str, Any]] = field(default_factory=list)

    # Additional metadata
    total_iterations: int = 0
    testbench_count: int = 0
    compile_retry_count: int = 0
    wall_time_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Log parsing
# ---------------------------------------------------------------------------

# Regex for API REQUEST header (tiktoken estimate, pre-call)
_REQUEST_HEADER_RE = re.compile(
    r'API REQUEST\s*\['
    r'API Call #(\d+)\s*\|\s*'
    r'Iter\s+(\d+)\s*\|\s*'
    r'Cumulative:\s*([\d.]+)%\s*\|\s*'
    r'Last:\s*([\d.]+)%\s*\|\s*'
    r'Failures:\s*(\d+)\s*\|\s*'
    r'No Progress:\s*(\d+)\s*\|\s*'
    r'Est\.\s*Input:\s*~?([\d,]+)\s*\]'
)

# Regex for AGENT RESPONSE header (API-reported token breakdown)
_RESPONSE_HEADER_RE = re.compile(
    r'AGENT RESPONSE\s*\['
    r'API Call #(\d+)\s*\|\s*'
    r'Iter\s+(\d+)\s*\|\s*'
    r'Cumulative:\s*([\d.]+)%\s*\|\s*'
    r'Last:\s*([\d.]+)%\s*\|\s*'
    r'In:\s*([\d,]+)\s*\(cached:\s*([\d,]+)\)\s*\|\s*'
    r'Out:\s*([\d,]+)\s*\(reasoning:\s*([\d,]+)\)\s*\|\s*'
    r'Total:\s*([\d,]+)\s*\]'
)

# Regex for tool call lines in AGENT RESPONSE (applied to content after prefix stripping)
_TOOL_CALL_NAME_RE = re.compile(r'^\s*\d+\.\s+(\w+)\s*$')
_TOOL_ARG_RE = re.compile(r'^\s{4,}(\w+):\s*(.*)$')

# Regex for timestamp
_TIMESTAMP_RE = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3})')

# Regex for stripping log prefix: "2026-02-22 16:33:07,244 - INFO:root:"
_LOG_PREFIX_RE = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}\s*-\s*\w+:\S+:')

# Regex for compile failure warnings
_COMPILE_FAIL_RE = re.compile(r'Compilation failed \(iter \d+, retry (\d+)\)')

# Regex for [TOOL NAME] lines in REQUEST blocks
_TOOL_NAME_RE = re.compile(r'\[TOOL NAME\]\s+(\w+)')


def parse_timestamp(line: str) -> Optional[str]:
    """Extract ISO timestamp from log line."""
    m = _TIMESTAMP_RE.match(line)
    if m:
        return f"{m.group(1)}.{m.group(2)}"
    return None


def strip_log_prefix(line: str) -> str:
    """Strip the timestamp/level/logger prefix from a log line to get message content.

    Input:  '2026-02-22 16:33:07,244 - INFO:root:     path: /foo/bar'
    Output: '     path: /foo/bar'

    Continuation lines (no prefix) are returned as-is.
    """
    m = _LOG_PREFIX_RE.match(line)
    if m:
        return line[m.end():]
    return line


def parse_run_log(log_path: Path) -> List[APICallRecord]:
    """
    Parse a run.log file and extract per-API-call records.

    Returns a list of APICallRecord, one per API call (REQUEST→RESPONSE pair).
    """
    records: Dict[int, APICallRecord] = {}  # keyed by api_call number

    with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    current_section = None  # 'request' or 'response'
    current_api_call = -1
    current_tool_name = None
    current_tool_args = {}
    collecting_tool_calls = False
    pending_tool_calls = []
    pending_tool_args = []

    for line in lines:
        stripped = line.strip()

        # Extract timestamp
        ts = parse_timestamp(stripped)

        # Get message content without the log prefix (for pattern matching)
        content = strip_log_prefix(stripped)

        # Detect API REQUEST header
        if 'API REQUEST' in stripped:
            # If we were collecting tool calls, finalize them before switching sections
            if collecting_tool_calls and current_tool_name:
                pending_tool_calls.append(current_tool_name)
                pending_tool_args.append(dict(current_tool_args))
            if collecting_tool_calls and current_api_call in records:
                records[current_api_call].tool_calls = list(pending_tool_calls)
                records[current_api_call].tool_args = list(pending_tool_args)
            collecting_tool_calls = False
            current_tool_name = None
            current_tool_args = {}

            m = _REQUEST_HEADER_RE.search(stripped)
            if m:
                api_call = int(m.group(1))
                current_section = 'request'
                current_api_call = api_call

                if api_call not in records:
                    records[api_call] = APICallRecord(api_call=api_call)

                rec = records[api_call]
                rec.iteration = int(m.group(2))
                rec.cumulative_coverage = float(m.group(3))
                rec.current_coverage = float(m.group(4))
                rec.failures = int(m.group(5))
                rec.no_progress = int(m.group(6))
                rec.request_tokens = int(m.group(7).replace(',', ''))
                if ts and not rec.request_time:
                    rec.request_time = ts
            continue

        # Detect AGENT RESPONSE header
        # NOTE: The framework increments api_calls BEFORE logging the response,
        # so RESPONSE "API Call #N" corresponds to REQUEST "API Call #(N-1)".
        # We pair them by storing response data on the record at api_call = N-1.
        if 'AGENT RESPONSE' in stripped:
            m = _RESPONSE_HEADER_RE.search(stripped)
            if m:
                response_api_call = int(m.group(1))
                # Map back to the matching request's api_call number
                paired_api_call = response_api_call - 1
                current_section = 'response'
                current_api_call = paired_api_call
                collecting_tool_calls = False
                current_tool_name = None
                current_tool_args = {}
                pending_tool_calls = []
                pending_tool_args = []

                if paired_api_call not in records:
                    records[paired_api_call] = APICallRecord(api_call=paired_api_call)

                rec = records[paired_api_call]
                rec.api_input_tokens = int(m.group(5).replace(',', ''))
                rec.api_cached_input_tokens = int(m.group(6).replace(',', ''))
                rec.api_output_tokens = int(m.group(7).replace(',', ''))
                rec.api_reasoning_tokens = int(m.group(8).replace(',', ''))
                rec.api_total_tokens = int(m.group(9).replace(',', ''))
                if ts:
                    rec.response_time = ts
            continue

            if '[TOOL CALLS]' in stripped:
                collecting_tool_calls = True
                current_tool_name = None
                current_tool_args = {}
                continue

            if collecting_tool_calls:
                # Use content (prefix-stripped) for matching tool names and args
                content_stripped = content.strip()

                # Check for tool name line (e.g., "  1. read_file")
                tm = _TOOL_CALL_NAME_RE.match(content_stripped)
                if tm:
                    # Save previous tool if any
                    if current_tool_name:
                        pending_tool_calls.append(current_tool_name)
                        pending_tool_args.append(dict(current_tool_args))
                    current_tool_name = tm.group(1)
                    current_tool_args = {}
                    continue

                # Check for tool argument line (use content with original indentation)
                am = _TOOL_ARG_RE.match(content)
                if am and current_tool_name:
                    current_tool_args[am.group(1)] = am.group(2)
                    continue

                # Check for section end: === line (content may start with ====)
                if content_stripped.startswith('=' * 10):
                    # Save last tool
                    if current_tool_name:
                        pending_tool_calls.append(current_tool_name)
                        pending_tool_args.append(dict(current_tool_args))

                    if current_api_call in records:
                        records[current_api_call].tool_calls = list(pending_tool_calls)
                        records[current_api_call].tool_args = list(pending_tool_args)

                    collecting_tool_calls = False
                    current_tool_name = None
                    current_tool_args = {}
                    current_section = None
                    continue

    # Sort by api_call number
    sorted_records = sorted(records.values(), key=lambda r: r.api_call)

    # Compute marginal tokens (forward-looking: context added BY this call)
    # Call N's tool results and LLM response inflate request_tokens[N+1].
    # So context_added_by[N] = request_tokens[N+1] - request_tokens[N].
    # This correctly attributes spec/RTL content to the read_file call,
    # testbench content to the write_file call, etc.
    for i, rec in enumerate(sorted_records):
        if i < len(sorted_records) - 1:
            next_rec = sorted_records[i + 1]
            rec.marginal_tokens = max(0, next_rec.request_tokens - rec.request_tokens)
        else:
            # Last call: use API-reported output tokens as marginal estimate
            rec.marginal_tokens = rec.api_output_tokens

    # Classify each record
    for rec in sorted_records:
        rec.category = classify_record(rec)

    return sorted_records


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_record(rec: APICallRecord) -> str:
    """
    Classify an API call record into a token usage category.

    Logic:
    1. If failures > 0 → error_recovery
    2. If write_file to testbenches/ → new_tb_generation
    3. If read_file (and no compile/sim/coverage) → spec_rtl_reading
    4. Everything else → overhead
    """
    # Error recovery: any call made while failures > 0
    if rec.failures > 0:
        return "error_recovery"

    tool_calls = rec.tool_calls
    tool_args = rec.tool_args

    has_write_file = "write_file" in tool_calls
    has_read_file = "read_file" in tool_calls
    has_compile = "compile_design" in tool_calls
    has_sim = "run_simulation" in tool_calls
    has_coverage = "parse_coverage" in tool_calls

    # Write file to testbenches/ = new TB generation
    if has_write_file:
        for i, name in enumerate(tool_calls):
            if name == "write_file" and i < len(tool_args):
                path = tool_args[i].get("path", "")
                if "testbenches/" in path and "report" not in path.lower():
                    return "new_tb_generation"
                elif "report" in path.lower():
                    return "overhead"
        return "overhead"

    # Read file only (no compile/sim/coverage) = spec/RTL reading
    if has_read_file and not has_compile and not has_sim and not has_coverage:
        return "spec_rtl_reading"

    # Compile, simulate, coverage = overhead
    if has_compile or has_sim or has_coverage:
        return "overhead"

    # No tool calls (reasoning only) = overhead
    return "overhead"


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate_analysis(
    design_name: str,
    records: List[APICallRecord],
    work_dir: Path
) -> DesignAnalysis:
    """Aggregate per-call records into a DesignAnalysis summary."""
    analysis = DesignAnalysis(design=design_name)

    # Load metadata from final_state.json if available
    state_path = work_dir / "final_state.json"
    if state_path.exists():
        try:
            with open(state_path, 'r') as f:
                state = json.load(f)
            analysis.model = state.get("config", {}).get("model", "unknown")
            analysis.final_coverage = state.get("cumulative_coverage", 0.0)
            analysis.total_iterations = state.get("iteration", 0)
            analysis.run_complete = state.get("done_reason") is not None or state.get("is_done", False)
        except (json.JSONDecodeError, KeyError):
            pass
    else:
        # No final_state.json — infer completeness from log: presence of signal_done
        # or write_file for report.md in the last few records
        if records:
            last_tools = []
            for r in records[-3:]:
                last_tools.extend(r.tool_calls)
            analysis.run_complete = "signal_done" in last_tools or any(
                "report" in str(a.get("path", "")).lower()
                for r in records[-3:] for a in r.tool_args
            )

    # If no final_state, extract from records
    if not records:
        return analysis

    if analysis.final_coverage == 0.0:
        # Use the highest cumulative coverage seen across all records
        analysis.final_coverage = max(r.cumulative_coverage for r in records)

    if analysis.total_iterations == 0:
        # Use the highest iteration number seen
        analysis.total_iterations = max(r.iteration for r in records)

    # Count testbenches
    tb_dir = work_dir / "testbenches"
    if tb_dir.exists():
        analysis.testbench_count = len(
            list(tb_dir.glob("*.sv")) + list(tb_dir.glob("*.v"))
        )

    # Count compile retries
    logs_dir = work_dir / "logs"
    if logs_dir.exists():
        analysis.compile_retry_count = len(list(logs_dir.glob("*_retry_*.log")))

    # Wall time
    if records[0].request_time and records[-1].response_time:
        try:
            t0 = datetime.strptime(records[0].request_time, "%Y-%m-%d %H:%M:%S.%f")
            t1 = datetime.strptime(records[-1].response_time, "%Y-%m-%d %H:%M:%S.%f")
            analysis.wall_time_seconds = (t1 - t0).total_seconds()
        except ValueError:
            pass

    analysis.total_api_calls = len(records)
    analysis.total_prompt_tokens_est = records[-1].request_tokens if records else 0  # tiktoken estimate at last request
    analysis.total_marginal_tokens = sum(r.marginal_tokens for r in records)

    # Aggregate by category
    cats = defaultdict(lambda: {
        "api_calls": 0, "marginal_tokens": 0,
        "api_input_tokens": 0, "api_output_tokens": 0, "api_reasoning_tokens": 0,
        "api_cached_input_tokens": 0, "api_total_tokens": 0,
    })
    for rec in records:
        cat = rec.category
        cats[cat]["api_calls"] += 1
        cats[cat]["marginal_tokens"] += rec.marginal_tokens
        cats[cat]["api_input_tokens"] += rec.api_input_tokens
        cats[cat]["api_output_tokens"] += rec.api_output_tokens
        cats[cat]["api_reasoning_tokens"] += rec.api_reasoning_tokens
        cats[cat]["api_cached_input_tokens"] += rec.api_cached_input_tokens
        cats[cat]["api_total_tokens"] += rec.api_total_tokens

    # Compute percentages
    total_marginal = analysis.total_marginal_tokens or 1
    total_api_total = sum(c["api_total_tokens"] for c in cats.values()) or 1
    for cat_name, cat_data in cats.items():
        cat_data["pct_marginal"] = round(cat_data["marginal_tokens"] / total_marginal * 100, 1)
        cat_data["pct_api_total"] = round(cat_data["api_total_tokens"] / total_api_total * 100, 1)

    # Ensure all 4 categories are present
    default_cat_template = {
        "api_calls": 0, "marginal_tokens": 0,
        "pct_marginal": 0.0, "pct_api_total": 0.0,
        "api_input_tokens": 0, "api_output_tokens": 0, "api_reasoning_tokens": 0,
        "api_cached_input_tokens": 0, "api_total_tokens": 0,
    }
    for default_cat in ("new_tb_generation", "spec_rtl_reading", "error_recovery", "overhead"):
        if default_cat not in cats:
            cats[default_cat] = dict(default_cat_template)

    analysis.categories = dict(cats)

    # Per-call records (cleaned for JSON output)
    analysis.per_call = []
    for rec in records:
        analysis.per_call.append({
            "api_call": rec.api_call,
            "iteration": rec.iteration,
            "category": rec.category,
            "failures": rec.failures,
            "cumulative_coverage": rec.cumulative_coverage,
            "request_tokens_est": rec.request_tokens,
            "marginal_tokens": rec.marginal_tokens,
            "api_input_tokens": rec.api_input_tokens,
            "api_cached_input_tokens": rec.api_cached_input_tokens,
            "api_output_tokens": rec.api_output_tokens,
            "api_reasoning_tokens": rec.api_reasoning_tokens,
            "api_total_tokens": rec.api_total_tokens,
            "tool_calls": rec.tool_calls,
            "request_time": rec.request_time,
            "response_time": rec.response_time,
        })

    return analysis


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def save_analysis(analysis: DesignAnalysis, output_path: Path):
    """Save analysis to JSON file."""
    data = {
        "design": analysis.design,
        "model": analysis.model,
        "total_api_calls": analysis.total_api_calls,
        "total_prompt_tokens_est": analysis.total_prompt_tokens_est,
        "total_marginal_tokens": analysis.total_marginal_tokens,
        "final_coverage": analysis.final_coverage,
        "run_complete": analysis.run_complete,
        "total_iterations": analysis.total_iterations,
        "testbench_count": analysis.testbench_count,
        "compile_retry_count": analysis.compile_retry_count,
        "wall_time_seconds": round(analysis.wall_time_seconds, 2),
        "categories": analysis.categories,
        "per_call": analysis.per_call,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)


def print_summary_table(analyses: List[DesignAnalysis]):
    """Print a human-readable summary table to stdout."""
    if not analyses:
        print("No designs analyzed.")
        return

    # Header
    print()
    print("=" * 130)
    print(f"{'Design':<30} {'Cov%':>6} {'API#':>5} {'Iter':>5} "
          f"{'Prompt':>9} {'Marg':>9} "
          f"{'NewTB':>8} {'Read':>8} {'ErrRec':>8} {'Over':>8} "
          f"{'Retries':>7} {'Time':>8}")
    print("-" * 130)

    for a in analyses:
        new_tb = a.categories.get("new_tb_generation", {})
        reading = a.categories.get("spec_rtl_reading", {})
        err_rec = a.categories.get("error_recovery", {})
        overhead = a.categories.get("overhead", {})

        def fmt_cat(cat_data):
            tokens = cat_data.get("marginal_tokens", 0)
            pct = cat_data.get("pct_marginal", 0.0)
            return f"{tokens:>5} ({pct:>4.0f}%)" if tokens > 0 else f"{'0':>5} ({0:>4.0f}%)"

        wall = a.wall_time_seconds
        if wall >= 3600:
            time_str = f"{wall/3600:.1f}h"
        elif wall >= 60:
            time_str = f"{wall/60:.1f}m"
        else:
            time_str = f"{wall:.0f}s"

        status = "✓" if a.run_complete else "✗"

        print(f"{a.design:<30} {a.final_coverage:>5.1f}% {a.total_api_calls:>5} {a.total_iterations:>5} "
              f"{a.total_prompt_tokens_est:>9,} {a.total_marginal_tokens:>9,} "
              f"{fmt_cat(new_tb):>8} {fmt_cat(reading):>8} {fmt_cat(err_rec):>8} {fmt_cat(overhead):>8} "
              f"{a.compile_retry_count:>7} {time_str:>7} {status}")

    print("=" * 130)

    # Aggregated totals
    total_marginal = sum(a.total_marginal_tokens for a in analyses)
    total_new_tb = sum(a.categories.get("new_tb_generation", {}).get("marginal_tokens", 0) for a in analyses)
    total_read = sum(a.categories.get("spec_rtl_reading", {}).get("marginal_tokens", 0) for a in analyses)
    total_err = sum(a.categories.get("error_recovery", {}).get("marginal_tokens", 0) for a in analyses)
    total_over = sum(a.categories.get("overhead", {}).get("marginal_tokens", 0) for a in analyses)

    print(f"\nAggregate across {len(analyses)} designs:")
    print(f"  Total marginal tokens: {total_marginal:,}")
    if total_marginal > 0:
        print(f"  new_tb_generation:     {total_new_tb:>8,} ({total_new_tb/total_marginal*100:>5.1f}%)")
        print(f"  spec_rtl_reading:      {total_read:>8,} ({total_read/total_marginal*100:>5.1f}%)")
        print(f"  error_recovery:        {total_err:>8,} ({total_err/total_marginal*100:>5.1f}%)")
        print(f"  overhead:              {total_over:>8,} ({total_over/total_marginal*100:>5.1f}%)")
    print()


def print_per_call_detail(analysis: DesignAnalysis):
    """Print detailed per-API-call breakdown for a single design."""
    print(f"\n{'='*150}")
    print(f"Per-Call Detail: {analysis.design}")
    print(f"{'='*150}")
    print(f"{'Call#':>5} {'Iter':>4} {'Cat':<20} {'Fail':>4} {'Cov%':>6} "
          f"{'EstIn':>8} {'Marginal':>8} "
          f"{'APIIn':>9} {'APICch':>9} {'APIOut':>9} {'APIRsn':>9} {'APITot':>9} {'Tools'}")
    print("-" * 150)

    for call in analysis.per_call:
        tools_str = ", ".join(call["tool_calls"]) if call["tool_calls"] else "(none)"
        est_in = call.get("request_tokens_est", 0)
        api_in = call.get("api_input_tokens", 0)
        api_cch = call.get("api_cached_input_tokens", 0)
        api_out = call.get("api_output_tokens", 0)
        api_rsn = call.get("api_reasoning_tokens", 0)
        api_tot = call.get("api_total_tokens", 0)
        print(f"{call['api_call']:>5} {call['iteration']:>4} {call['category']:<20} "
              f"{call['failures']:>4} {call['cumulative_coverage']:>5.1f}% "
              f"{est_in:>8,} {call['marginal_tokens']:>8,} "
              f"{api_in:>9,} {api_cch:>9,} {api_out:>9,} {api_rsn:>9,} {api_tot:>9,} {tools_str}")

    print(f"{'='*150}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def find_designs(react_dir: Path) -> List[str]:
    """Find all design directories containing a run.log file."""
    designs = []
    if not react_dir.exists():
        return designs
    for d in sorted(react_dir.iterdir()):
        if d.is_dir() and (d / "run.log").exists():
            designs.append(d.name)
    return designs


def analyze_design(design_name: str, react_dir: Path, output_dir: Optional[Path] = None) -> DesignAnalysis:
    """Analyze a single design's run.log and produce a DesignAnalysis."""
    work_dir = react_dir / design_name
    log_path = work_dir / "run.log"

    if not log_path.exists():
        print(f"WARNING: No run.log found for {design_name} at {log_path}", file=sys.stderr)
        return DesignAnalysis(design=design_name)

    records = parse_run_log(log_path)
    analysis = aggregate_analysis(design_name, records, work_dir)

    # Save JSON output
    if output_dir:
        out_path = output_dir / f"{design_name}_token_analysis.json"
    else:
        out_path = work_dir / "token_analysis.json"
    save_analysis(analysis, out_path)

    return analysis


def main():
    parser = argparse.ArgumentParser(
        description="Analyze LLM token usage by category from agent run logs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Categories:
  new_tb_generation  - Writing new testbenches for coverage closure
  spec_rtl_reading   - Reading specification/RTL files
  error_recovery     - Fixing compilation/simulation errors
  overhead           - Compile, simulate, parse coverage, report writing

Token Attribution:
  Marginal cost: each API call is charged only the delta tokens added since
  the previous call, avoiding double-counting the growing conversation context.

Examples:
  python scripts/analyze_tokens.py --all
  python scripts/analyze_tokens.py --design sha1_top --detail
  python scripts/analyze_tokens.py --design sha1_top chacha_top --output-dir results/

Caveats:
  - Token counts are tiktoken estimates (prompt-side only for existing logs)
  - API-reported token counts (input/output/reasoning/cached) come from the AGENT RESPONSE header
  - API-reported token counts require framework instrumentation (see docs)
        """
    )

    parser.add_argument(
        '--all', action='store_true',
        help='Analyze all designs in work/ReAct/'
    )
    parser.add_argument(
        '--design', nargs='+', metavar='NAME',
        help='Design name(s) to analyze (subdirectories of work/ReAct/)'
    )
    parser.add_argument(
        '--react-dir', type=str, default=None,
        help='Path to ReAct work directory (default: work/ReAct/)'
    )
    parser.add_argument(
        '--output-dir', type=str, default=None,
        help='Directory for JSON output files (default: per-design work dir)'
    )
    parser.add_argument(
        '--detail', action='store_true',
        help='Print per-API-call detail table'
    )
    parser.add_argument(
        '--json-summary', action='store_true',
        help='Print aggregate summary as JSON to stdout'
    )

    args = parser.parse_args()

    if not args.all and not args.design:
        parser.error("Specify --all or --design NAME [NAME ...]")

    # Resolve paths
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent

    if args.react_dir:
        react_dir = Path(args.react_dir)
    else:
        react_dir = project_root / "work" / "ReAct"

    if not react_dir.exists():
        print(f"Error: ReAct directory not found: {react_dir}", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir) if args.output_dir else None

    # Determine designs to analyze
    if args.all:
        design_names = find_designs(react_dir)
        if not design_names:
            print(f"No designs found in {react_dir}", file=sys.stderr)
            return 1
        print(f"Found {len(design_names)} designs: {', '.join(design_names)}")
    else:
        design_names = args.design

    # Analyze each design
    analyses = []
    for name in design_names:
        print(f"Analyzing {name}...", end=" ", flush=True)
        analysis = analyze_design(name, react_dir, output_dir)
        analyses.append(analysis)
        out_path = (output_dir / f"{name}_token_analysis.json") if output_dir else (react_dir / name / "token_analysis.json")
        print(f"done ({analysis.total_api_calls} calls, {analysis.total_marginal_tokens:,} marginal tokens → {out_path})")

    # Print summary table
    print_summary_table(analyses)

    # Print details if requested
    if args.detail:
        for a in analyses:
            print_per_call_detail(a)

    # JSON summary to stdout
    if args.json_summary:
        summary = []
        for a in analyses:
            summary.append({
                "design": a.design,
                "model": a.model,
                "total_api_calls": a.total_api_calls,
                "total_marginal_tokens": a.total_marginal_tokens,
                "final_coverage": a.final_coverage,
                "categories": a.categories,
            })
        print(json.dumps(summary, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
