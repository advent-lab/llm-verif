#!/usr/bin/env python3
"""Parse a Codex CLI session JSONL log and extract token usage breakdown.

Usage:
    python scripts/analyze_codex_session.py <path_to_session.jsonl>
    python scripts/analyze_codex_session.py <path1.jsonl> <path2.jsonl> ...
    python scripts/analyze_codex_session.py --dir /home/user/.codex/sessions/2026/02/23/
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime


def parse_session(path: Path) -> dict:
    """Parse a single Codex session JSONL file and extract token usage.

    Returns a dict with session metadata and per-turn + cumulative token usage.
    """
    result = {
        "path": str(path),
        "session_id": None,
        "model": None,
        "start_time": None,
        "end_time": None,
        "turns": [],           # per-turn token_count snapshots
        "total_usage": None,   # final cumulative usage
    }

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts = obj.get("timestamp")
            evt_type = obj.get("type")
            payload = obj.get("payload", {})

            # Session metadata
            if evt_type == "session_meta":
                result["session_id"] = payload.get("id")
                result["start_time"] = payload.get("timestamp")

            # Model from turn_context
            if evt_type == "turn_context" and result["model"] is None:
                result["model"] = payload.get("model")

            # Token counts
            if evt_type == "event_msg" and payload.get("type") == "token_count":
                info = payload.get("info")
                if info is None:
                    continue

                total = info.get("total_token_usage", {})
                last = info.get("last_token_usage", {})

                # Only record if this represents a new cumulative total
                # (avoid duplicates — multiple token_count events can share the same totals)
                if result["turns"]:
                    prev_total = result["turns"][-1]["cumulative"]
                    if prev_total == total:
                        continue

                result["turns"].append({
                    "timestamp": ts,
                    "cumulative": dict(total),
                    "this_turn": dict(last),
                })
                result["total_usage"] = dict(total)
                result["end_time"] = ts

    return result


def format_tokens(n: int) -> str:
    """Format token count with comma separators."""
    return f"{n:,}"


def print_session_report(session: dict):
    """Print a human-readable report for one session."""
    total = session.get("total_usage")
    if not total:
        print(f"  {session['path']}: No token usage data found.\n")
        return

    model = session.get("model", "unknown")
    sid = session.get("session_id", "unknown")

    # Wall time
    wall_str = ""
    if session["start_time"] and session["end_time"]:
        try:
            fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
            t0 = datetime.strptime(session["start_time"], fmt)
            t1 = datetime.strptime(session["end_time"], fmt)
            secs = (t1 - t0).total_seconds()
            if secs >= 3600:
                wall_str = f"{secs/3600:.1f}h"
            elif secs >= 60:
                wall_str = f"{secs/60:.1f}m"
            else:
                wall_str = f"{secs:.0f}s"
        except ValueError:
            pass

    input_tok = total.get("input_tokens", 0)
    cached_tok = total.get("cached_input_tokens", 0)
    output_tok = total.get("output_tokens", 0)
    reasoning_tok = total.get("reasoning_output_tokens", 0)
    total_tok = total.get("total_tokens", 0)
    non_reasoning_output = output_tok - reasoning_tok

    print(f"{'='*70}")
    print(f"Session: {sid}")
    print(f"Model:   {model}")
    print(f"File:    {session['path']}")
    if wall_str:
        print(f"Duration: {wall_str}")
    print(f"API Turns: {len(session['turns'])}")
    print(f"{'='*70}")

    print(f"\n  CUMULATIVE TOKEN USAGE (end of conversation)")
    print(f"  {'─'*50}")
    print(f"  {'Input tokens:':<30} {format_tokens(input_tok):>12}")
    print(f"    {'Cached:':<28} {format_tokens(cached_tok):>12}  ({cached_tok/max(input_tok,1)*100:.1f}%)")
    print(f"    {'Uncached:':<28} {format_tokens(input_tok - cached_tok):>12}  ({(input_tok-cached_tok)/max(input_tok,1)*100:.1f}%)")
    print(f"  {'Output tokens:':<30} {format_tokens(output_tok):>12}")
    print(f"    {'Reasoning:':<28} {format_tokens(reasoning_tok):>12}  ({reasoning_tok/max(output_tok,1)*100:.1f}%)")
    print(f"    {'Non-reasoning:':<28} {format_tokens(non_reasoning_output):>12}  ({non_reasoning_output/max(output_tok,1)*100:.1f}%)")
    print(f"  {'─'*50}")
    print(f"  {'Total tokens:':<30} {format_tokens(total_tok):>12}")

    # Per-turn breakdown
    turns = session["turns"]
    if turns:
        print(f"\n  PER-TURN BREAKDOWN ({len(turns)} turns)")
        print(f"  {'─'*66}")
        print(f"  {'Turn':>5} {'Input':>10} {'Cached':>10} {'Output':>10} {'Reasoning':>10} {'Total':>10}")
        print(f"  {'─'*66}")
        for i, turn in enumerate(turns, 1):
            t = turn["this_turn"]
            print(f"  {i:>5} {t.get('input_tokens',0):>10,} {t.get('cached_input_tokens',0):>10,} "
                  f"{t.get('output_tokens',0):>10,} {t.get('reasoning_output_tokens',0):>10,} "
                  f"{t.get('total_tokens',0):>10,}")
        print(f"  {'─'*66}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Extract token usage from Codex CLI session JSONL logs"
    )
    parser.add_argument("paths", nargs="*", help="Path(s) to .jsonl session log files")
    parser.add_argument("--dir", type=str, default=None,
                        help="Directory to scan for .jsonl session logs")
    args = parser.parse_args()

    paths = []
    if args.dir:
        dir_path = Path(args.dir)
        paths.extend(sorted(dir_path.rglob("*.jsonl")))
    for p in (args.paths or []):
        paths.append(Path(p))

    if not paths:
        parser.print_help()
        sys.exit(1)

    sessions = []
    for p in paths:
        if not p.exists():
            print(f"WARNING: {p} does not exist, skipping.")
            continue
        sessions.append(parse_session(p))

    for s in sessions:
        print_session_report(s)

    # Summary across all sessions if multiple
    if len(sessions) > 1:
        print(f"{'='*70}")
        print(f"AGGREGATE ACROSS {len(sessions)} SESSIONS")
        print(f"{'='*70}")
        agg = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0,
               "reasoning_output_tokens": 0, "total_tokens": 0}
        for s in sessions:
            t = s.get("total_usage") or {}
            for k in agg:
                agg[k] += t.get(k, 0)
        print(f"  {'Input tokens:':<30} {format_tokens(agg['input_tokens']):>12}")
        print(f"    {'Cached:':<28} {format_tokens(agg['cached_input_tokens']):>12}")
        print(f"  {'Output tokens:':<30} {format_tokens(agg['output_tokens']):>12}")
        print(f"    {'Reasoning:':<28} {format_tokens(agg['reasoning_output_tokens']):>12}")
        print(f"  {'Total tokens:':<30} {format_tokens(agg['total_tokens']):>12}")
        print()


if __name__ == "__main__":
    main()
