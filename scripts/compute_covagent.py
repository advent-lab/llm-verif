#!/usr/bin/env python3
import argparse
import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

DESIGN_PATH_PATTERNS = ["spec/", "design/", "design_context/", "rtl/"]


def format_duration(secs: float) -> str:
    if secs >= 3600:
        return f"{secs / 3600:.1f}h"
    elif secs >= 60:
        return f"{secs / 60:.1f}m"
    return f"{secs:.0f}s"


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


class Category(str, Enum):
    SYSTEM_PROMPT = "System Prompt"
    DESIGN_COMPREHENSION = "Design Comprehension"
    STIMULUS_GENERATION = "Stimulus Generation"
    COVERAGE_FEEDBACK = "Coverage Feedback"
    ERROR_RECOVERY = "Error Recovery"
    AGENTIC_OVERHEAD = "Agentic Overhead"




# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------


@dataclass
class TurnRecord:
    """Per-turn record with split input/output categorization."""

    turn: int

    # Raw token counts from token_count event (last_usage)
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cached_input_tokens: int = 0
    total_tokens: int = 0  # context window (input + output)

    # Derived
    new_input_tokens: int = 0

    # Categories
    input_category: Category = Category.AGENTIC_OVERHEAD
    output_category: Category = Category.AGENTIC_OVERHEAD

    # Context from events
    tool_calls: List[str] = field(default_factory=list)
    tool_args: List[Dict] = field(default_factory=list)
    consecutive_failures: int = 0
    is_finalizing: bool = False
    iteration: int = 1
    coverage_pct: float = 0.0


@dataclass
class CovAgentResult:
    """Analysis result with split input/output categorization."""

    design: str = ""
    model: str = ""
    log_path: str = ""
    duration_seconds: float = 0.0
    final_coverage: float = 0.0
    total_turns: int = 0
    total_iterations: int = 0

    # Token totals
    final_context_tokens: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_reasoning_tokens: int = 0
    total_cached_tokens: int = 0
    cache_hit_rate: float = 0.0

    # Per-category summary
    by_category: Dict[str, Dict] = field(default_factory=dict)

    # Per-turn breakdown
    per_turn: List[Dict] = field(default_factory=list)

    # Coverage curve
    coverage_curve: List[Dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "design": self.design,
            "model": self.model,
            "log_path": self.log_path,
            "duration_seconds": round(self.duration_seconds, 2),
            "final_coverage": round(self.final_coverage, 2),
            "total_turns": self.total_turns,
            "total_iterations": self.total_iterations,
            "final_context_tokens": self.final_context_tokens,
            "tokens": {
                "input": self.total_input_tokens,
                "output": self.total_output_tokens,
                "reasoning": self.total_reasoning_tokens,
                "cached_input": self.total_cached_tokens,
                "cache_hit_rate": round(self.cache_hit_rate, 4),
            },
            "by_category": self.by_category,
            "per_turn": self.per_turn,
            "coverage_curve": self.coverage_curve,
        }


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class CovAgentParser:
    """Parse events.jsonl with split input/output token categorization."""

    def __init__(self, log_path: str):
        self.log_path = Path(log_path)
        self.turns: List[TurnRecord] = []
        self._meta: Dict[str, Any] = {}
        self._finalize_before_api_call: Optional[int] = None

    def parse(self) -> None:
        """Parse events.jsonl and build classified TurnRecord list."""
        api_calls: Dict[int, Dict[str, Any]] = {}
        current_failures = 0
        current_iteration = 1
        current_coverage = 0.0
        is_finalizing = False
        finalize_ts: Optional[str] = None

        with open(self.log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                event = obj["event"]
                data = obj.get("data", {})

                if event == "session_start":
                    cfg = data.get("config", {})
                    self._meta = {
                        "design": cfg.get("design_name", ""),
                        "model": cfg.get("model", "unknown"),
                    }

                elif event == "session_end":
                    self._meta["duration_seconds"] = data.get("duration_seconds", 0)
                    self._meta["final_coverage"] = data.get("final_coverage", 0.0)
                    self._meta["total_iterations"] = data.get("iterations", 0)

                elif event == "api_request":
                    ac = data["api_call"]
                    current_failures = data.get("consecutive_failures", 0)
                    if ac not in api_calls:
                        api_calls[ac] = {
                            "api_call": ac,
                            "iteration": data.get("iteration", current_iteration),
                            "consecutive_failures": current_failures,
                            "coverage_pct": data.get(
                                "cumulative_coverage", current_coverage
                            ),
                            "tool_calls": [],
                            "tool_args": [],
                        }
                    else:
                        api_calls[ac]["consecutive_failures"] = current_failures

                elif event == "tool_call":
                    ac = data["api_call"]
                    if ac not in api_calls:
                        api_calls[ac] = {
                            "api_call": ac,
                            "tool_calls": [],
                            "tool_args": [],
                        }
                    api_calls[ac]["tool_calls"].append(data["tool_name"])
                    api_calls[ac]["tool_args"].append(data.get("arguments", {}))

                elif event == "token_count":
                    ac = data["api_call"]
                    usage = data.get("last_usage", {})
                    if ac not in api_calls:
                        api_calls[ac] = {
                            "api_call": ac,
                            "tool_calls": [],
                            "tool_args": [],
                        }
                    api_calls[ac]["input_tokens"] = usage.get("input_tokens", 0)
                    api_calls[ac]["output_tokens"] = usage.get("output_tokens", 0)
                    api_calls[ac]["reasoning_tokens"] = usage.get(
                        "reasoning_tokens", 0
                    )
                    api_calls[ac]["cached_input_tokens"] = usage.get(
                        "cached_input_tokens", 0
                    )
                    api_calls[ac]["total_tokens"] = usage.get("total_tokens", 0)

                elif event == "state_update":
                    current_iteration = data.get("iteration", current_iteration)
                    current_failures = data.get("consecutive_failures", 0)
                    current_coverage = data.get(
                        "cumulative_coverage", current_coverage
                    )
                    is_finalizing = data.get("is_finalizing", False)
                    ac_num = data.get("api_calls", 0)
                    if ac_num in api_calls:
                        api_calls[ac_num]["coverage_pct"] = current_coverage
                        api_calls[ac_num]["iteration"] = current_iteration
                        api_calls[ac_num]["is_finalizing"] = is_finalizing
                        # Track failures at time of state_update for this turn
                        api_calls[ac_num]["state_failures"] = current_failures

                elif event == "human_message":
                    if data.get("source") == "finalize":
                        finalize_ts = obj.get("ts")

                elif event == "finalize":
                    finalize_ts = obj.get("ts")

        # Determine which api_call the finalize message was injected before
        if finalize_ts:
            sorted_acs = sorted(api_calls.keys())
            for ac_num in sorted_acs:
                ac_data = api_calls[ac_num]
                if ac_data.get("is_finalizing", False):
                    self._finalize_before_api_call = ac_num
                    break

        # Build ordered TurnRecords
        sorted_keys = sorted(api_calls.keys())
        for ac_num in sorted_keys:
            d = api_calls[ac_num]
            rec = TurnRecord(
                turn=d["api_call"],
                input_tokens=d.get("input_tokens", 0),
                output_tokens=d.get("output_tokens", 0),
                reasoning_tokens=d.get("reasoning_tokens", 0),
                cached_input_tokens=d.get("cached_input_tokens", 0),
                total_tokens=d.get("total_tokens", 0),
                tool_calls=d.get("tool_calls", []),
                tool_args=d.get("tool_args", []),
                consecutive_failures=d.get("consecutive_failures", 0),
                is_finalizing=d.get("is_finalizing", False),
                iteration=d.get("iteration", 1),
                coverage_pct=d.get("coverage_pct", 0.0),
            )
            self.turns.append(rec)

        # Compute new_input_tokens and classify
        for i, turn in enumerate(self.turns):
            if i == 0:
                turn.new_input_tokens = turn.input_tokens
            else:
                prev = self.turns[i - 1]
                prev_visible_output = prev.output_tokens - prev.reasoning_tokens
                turn.new_input_tokens = (
                    turn.input_tokens - prev.input_tokens - prev_visible_output
                )
                if turn.new_input_tokens < 0:
                    print(
                        f"  Warning: negative new_input_tokens at turn {turn.turn} "
                        f"({turn.new_input_tokens}), clamping to 0",
                        file=sys.stderr,
                    )
                    turn.new_input_tokens = 0

            turn.input_category = self._classify_input(i)
            turn.output_category = self._classify_output(turn)

    def _classify_input(self, turn_idx: int) -> Category:
        """Classify input tokens based on previous turn's tool results."""
        if turn_idx == 0:
            return Category.SYSTEM_PROMPT

        prev = self.turns[turn_idx - 1]
        current = self.turns[turn_idx]

        # D: Error recovery takes precedence
        if prev.consecutive_failures > 0:
            return Category.ERROR_RECOVERY

        # Check for finalize injection
        if (
            self._finalize_before_api_call is not None
            and current.turn == self._finalize_before_api_call
        ):
            return Category.AGENTIC_OVERHEAD

        # C: Previous turn produced coverage feedback
        if "run_verification_cycle" in prev.tool_calls:
            return Category.COVERAGE_FEEDBACK
        if "parse_coverage" in prev.tool_calls:
            return Category.COVERAGE_FEEDBACK

        # A: Previous turn read design files
        if self._has_design_read(prev.tool_calls, prev.tool_args):
            return Category.DESIGN_COMPREHENSION

        # B: Previous turn wrote testbench (result enters context)
        if self._has_testbench_write(prev.tool_calls, prev.tool_args):
            return Category.STIMULUS_GENERATION

        return Category.AGENTIC_OVERHEAD

    def _classify_output(self, turn: TurnRecord) -> Category:
        """Classify output tokens based on this turn's actions."""
        # E: Finalizing
        if turn.is_finalizing:
            return Category.AGENTIC_OVERHEAD

        # D: Error recovery takes precedence
        if turn.consecutive_failures > 0:
            return Category.ERROR_RECOVERY

        # B: Stimulus generation
        if "run_verification_cycle" in turn.tool_calls:
            return Category.STIMULUS_GENERATION
        if self._has_testbench_write(turn.tool_calls, turn.tool_args):
            return Category.STIMULUS_GENERATION

        # A: Design comprehension
        if self._has_design_read(turn.tool_calls, turn.tool_args):
            return Category.DESIGN_COMPREHENSION

        return Category.AGENTIC_OVERHEAD

    @staticmethod
    def _has_design_read(tool_calls: List[str], tool_args: List[Dict]) -> bool:
        """Check if any tool call reads a design/spec/rtl/design_context file."""
        for i, tool in enumerate(tool_calls):
            if tool == "read_file" and i < len(tool_args):
                path = str(tool_args[i].get("path", ""))
                if any(p in path for p in DESIGN_PATH_PATTERNS):
                    return True
        return False

    @staticmethod
    def _has_testbench_write(tool_calls: List[str], tool_args: List[Dict]) -> bool:
        """Check if any tool call writes a testbench file."""
        for i, tool in enumerate(tool_calls):
            if tool == "write_file" and i < len(tool_args):
                path = str(tool_args[i].get("path", ""))
                if (
                    "testbenches/" in path
                    and path.endswith(".sv")
                    and "report" not in path.lower()
                ):
                    return True
        return False

    def build_result(self) -> CovAgentResult:
        """Build analysis result from parsed turns."""
        self.parse()

        result = CovAgentResult(
            design=self._meta.get("design", ""),
            model=self._meta.get("model", "unknown"),
            log_path=str(self.log_path),
            duration_seconds=self._meta.get("duration_seconds", 0.0),
            final_coverage=self._meta.get("final_coverage", 0.0),
            total_turns=len(self.turns),
            total_iterations=self._meta.get("total_iterations", 0),
        )

        if self.turns:
            result.final_context_tokens = self.turns[-1].total_tokens
            result.total_input_tokens = sum(t.input_tokens for t in self.turns)
            result.total_output_tokens = sum(t.output_tokens for t in self.turns)
            result.total_reasoning_tokens = sum(t.reasoning_tokens for t in self.turns)
            result.total_cached_tokens = sum(t.cached_input_tokens for t in self.turns)
            if result.total_input_tokens > 0:
                result.cache_hit_rate = (
                    result.total_cached_tokens / result.total_input_tokens
                )

        result.by_category = self._compute_category_breakdown()
        result.per_turn = self._build_per_turn()
        result.coverage_curve = self._build_coverage_curve()

        return result

    def _compute_category_breakdown(self) -> Dict[str, Dict]:
        """Compute per-category aggregation with split input/output."""
        final_ctx = self.turns[-1].total_tokens if self.turns else 1
        breakdown = {}

        for cat in Category:
            # Input side: turns where input_category == cat
            in_turns = [t for t in self.turns if t.input_category == cat]
            cat_input = sum(t.new_input_tokens for t in in_turns)

            # Output side: turns where output_category == cat
            out_turns = [t for t in self.turns if t.output_category == cat]
            cat_reasoning = sum(t.reasoning_tokens for t in out_turns)
            cat_total_output = sum(t.output_tokens for t in out_turns)
            cat_visible_output = cat_total_output - cat_reasoning

            cat_total = cat_input + cat_total_output

            breakdown[cat.value] = {
                "name": cat.value,
                "input_tokens": cat_input,
                "visible_output_tokens": cat_visible_output,
                "reasoning_tokens": cat_reasoning,
                "total_output_tokens": cat_total_output,
                "total_tokens": cat_total,
                "pct_of_final_context": round(cat_total / final_ctx, 4)
                if final_ctx > 0
                else 0.0,
                "num_turns_input": len(in_turns),
                "num_turns_output": len(out_turns),
            }

        return breakdown

    def _build_per_turn(self) -> List[Dict]:
        """Build per-turn breakdown matching the reference table format."""
        rows = []
        for t in self.turns:
            rows.append(
                {
                    "turn": t.turn,
                    "cached": t.cached_input_tokens,
                    "new_input": t.new_input_tokens,
                    "input_category": t.input_category.value,
                    "output": t.output_tokens,
                    "output_category": t.output_category.value,
                    "reasoning": t.reasoning_tokens,
                    "total_accum": t.total_tokens,
                    "iteration": t.iteration,
                    "coverage_pct": t.coverage_pct,
                    "consecutive_failures": t.consecutive_failures,
                    "is_finalizing": t.is_finalizing,
                    "tool_calls": t.tool_calls,
                }
            )
        return rows

    def _build_coverage_curve(self) -> List[Dict]:
        """Build coverage vs tokens curve data points."""
        curve = []
        for t in self.turns:
            curve.append(
                {
                    "turn": t.turn,
                    "total_tokens": t.total_tokens,
                    "coverage_pct": t.coverage_pct,
                }
            )
        return curve




# ---------------------------------------------------------------------------
# Console Output
# ---------------------------------------------------------------------------




def print_category_summary(result: CovAgentResult) -> None:
    """Print per-category summary table."""
    print(f"\nDesign:    {result.design}")
    print(f"Model:     {result.model}")
    print(f"Coverage:  {result.final_coverage:.1f}%")
    print(f"Turns:     {result.total_turns}")
    print(f"Iter:      {result.total_iterations}")
    print(f"Duration:  {format_duration(result.duration_seconds)}")
    print(f"Final Ctx: {result.final_context_tokens} tokens")

    t = result.to_dict()["tokens"]
    print(f"\nToken Totals:")
    print(f"Input:     {t['input']:>10}")
    print(f"Output:    {t['output']:>10}")
    print(f"Reasoning: {t['reasoning']:>10}")
    print(f"Cached:    {t['cached_input']:>10}")
    print(f"Cache Hit: {t['cache_hit_rate'] * 100:>9.1f}%")

    print(
        f"\n  {'Category':<30} {'In Tok':>8} {'Vis Out':>8} {'Reason':>8} "
        f"{'Tot Out':>8} {'% Ctx':>7} {'#In':>4} {'#Out':>4}"
    )
    print(f"  {'-' * 90}")

    for cat in Category:
        c = result.by_category.get(cat.value, {})
        label = cat.value
        print(
            f"  {label:<30} "
            f"{c.get('input_tokens', 0):>8} "
            f"{c.get('visible_output_tokens', 0):>8} "
            f"{c.get('reasoning_tokens', 0):>8} "
            f"{c.get('total_output_tokens', 0):>8} "
            f"{c.get('pct_of_final_context', 0) * 100:>6.1f}% "
            f"{c.get('num_turns_input', 0):>4} "
            f"{c.get('num_turns_output', 0):>4}"
        )

    # Totals row
    total_in = sum(c.get("input_tokens", 0) for c in result.by_category.values())
    total_vis = sum(
        c.get("visible_output_tokens", 0) for c in result.by_category.values()
    )
    total_rsn = sum(c.get("reasoning_tokens", 0) for c in result.by_category.values())
    total_out = sum(
        c.get("total_output_tokens", 0) for c in result.by_category.values()
    )
    total_pct = sum(
        c.get("pct_of_final_context", 0) for c in result.by_category.values()
    )
    print(f"  {'-' * 90}")
    print(
        f"  {'TOTAL':<30} "
        f"{total_in:>8} "
        f"{total_vis:>8} "
        f"{total_rsn:>8} "
        f"{total_out:>8} "
        f"{total_pct * 100:>6.1f}% "
        f"{result.total_turns:>4} "
        f"{result.total_turns:>4}"
    )
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="CovAgent Compute Analysis: split input/output token categorization.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s work/trng_top
  %(prog)s work/chacha_top
        """,
    )
    parser.add_argument("work_dir", help="Path to work directory containing events.jsonl")
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Suppress JSON output, only print console tables",
    )

    args = parser.parse_args()

    work_dir = Path(args.work_dir)
    events_path = work_dir / "events.jsonl"

    if not events_path.exists():
        print(f"Error: events.jsonl not found in {work_dir}", file=sys.stderr)
        return 1

    p = CovAgentParser(str(events_path))
    result = p.build_result()

    # Print category summary
    print_category_summary(result)

    # JSON output
    if not args.no_json:
        out_name = f"tokens.json"
        out_path = work_dir / out_name
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"Wrote {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
