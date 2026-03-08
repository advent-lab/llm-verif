#!/usr/bin/env python3
"""Codex CLI Compute Analysis: Split input/output token categorization.

Parses Codex .jsonl logs and independently categorizes input and output
tokens of each agent turn into 6 activity categories:

  S - System Prompt:        Turn 1 input (system message)
  A - Design Comprehension: Reading spec/RTL/design files
  B - Stimulus Generation:  Writing/revising testbenches (apply_patch)
  C - Coverage Feedback:    Running/reading coverage reports
  D - Error Recovery:       Actions while recovering from compile/sim failures
  E - Agentic Overhead:     Orchestration, env setup, compile, simulate, etc.

Usage:
    python scripts/compute_codex.py codex_logs/trng_top.jsonl
    python scripts/compute_codex.py codex_logs/trng_top.jsonl --no-json
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))
from compute_study import DESIGN_PATH_PATTERNS, format_duration


# ---------------------------------------------------------------------------
# Categories (shared with compute_covagent)
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

    # Raw token counts from last_token_usage
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cached_input_tokens: int = 0
    total_tokens: int = 0

    # Derived
    new_input_tokens: int = 0

    # Categories
    input_category: Category = Category.AGENTIC_OVERHEAD
    output_category: Category = Category.AGENTIC_OVERHEAD

    # Context from events
    tool_name: str = ""
    cmd: str = ""
    patch_target: str = ""
    in_error_state: bool = False
    coverage_pct: float = 0.0


@dataclass
class CodexResult:
    """Analysis result with split input/output categorization."""

    design: str = ""
    model: str = ""
    log_path: str = ""
    duration_seconds: float = 0.0
    final_coverage: float = 0.0
    total_turns: int = 0

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
            "framework": "codex",
            "design": self.design,
            "model": self.model,
            "log_path": self.log_path,
            "duration_seconds": round(self.duration_seconds, 2),
            "final_coverage": round(self.final_coverage, 2),
            "total_turns": self.total_turns,
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


class CodexParser:
    """Parse Codex .jsonl with split input/output token categorization."""

    def __init__(self, log_path: str):
        self.log_path = Path(log_path)
        self.turns: List[TurnRecord] = []
        self._meta: Dict[str, Any] = {}

    def parse(self) -> None:
        """Parse .jsonl and build classified TurnRecord list."""
        with open(self.log_path, encoding="utf-8") as f:
            events = [json.loads(line.strip()) for line in f if line.strip()]

        # Extract session metadata
        self._extract_meta(events)

        # Build raw turn data by deduplicating token_count events
        raw_turns = self._extract_turns(events)

        # Build TurnRecords
        for i, rt in enumerate(raw_turns):
            rec = TurnRecord(
                turn=i + 1,
                input_tokens=rt["input_tokens"],
                output_tokens=rt["output_tokens"],
                reasoning_tokens=rt["reasoning_tokens"],
                cached_input_tokens=rt["cached_input_tokens"],
                total_tokens=rt["total_tokens"],
                tool_name=rt["tool_name"],
                cmd=rt["cmd"],
                patch_target=rt["patch_target"],
                in_error_state=rt["in_error_state"],
                coverage_pct=rt["coverage_pct"],
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

    def _extract_meta(self, events: list) -> None:
        """Extract session metadata from events."""
        self._meta["model"] = "unknown"
        self._meta["design"] = ""

        first_ts = None
        last_ts = None

        for obj in events:
            ts = obj.get("timestamp")
            if ts:
                if first_ts is None:
                    first_ts = ts
                last_ts = ts

            if obj["type"] == "session_meta":
                payload = obj["payload"]
                self._meta["model"] = payload.get("model_provider", "unknown")

            elif obj["type"] == "turn_context":
                payload = obj["payload"]
                model = payload.get("model", "")
                if model:
                    self._meta["model"] = model

            elif obj["type"] == "response_item":
                payload = obj["payload"]
                if payload.get("type") == "message" and payload.get("role") == "user":
                    content = payload.get("content", [])
                    for c in content:
                        text = c.get("text", "")
                        m = re.search(r"Design Name:\s*(\S+)", text)
                        if m:
                            self._meta["design"] = m.group(1)

        # Duration from timestamps
        if first_ts and last_ts:
            from datetime import datetime

            try:
                t0 = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                self._meta["duration_seconds"] = (t1 - t0).total_seconds()
            except (ValueError, TypeError):
                self._meta["duration_seconds"] = 0.0

    def _extract_turns(self, events: list) -> List[Dict]:
        """Extract deduplicated turns from events.

        Each turn corresponds to one unique token_count event (dedup by
        total_token_usage.total_tokens). Maps each to its preceding
        function_call and following function_call_output.
        """
        # Collect all events with their indices
        # Build a map: event_index -> event for quick lookup
        turns = []
        seen_totals = set()
        error_state = False
        latest_coverage = 0.0

        # Pre-scan: collect function_call info and outputs by their position
        func_calls = {}  # index -> {name, cmd, args}
        func_outputs = {}  # index -> output string
        patch_calls = {}  # index -> {name}
        patch_outputs = {}  # index -> output string

        for i, obj in enumerate(events):
            if obj["type"] == "response_item":
                pt = obj["payload"].get("type", "")
                if pt == "function_call":
                    name = obj["payload"].get("name", "")
                    args_str = obj["payload"].get("arguments", "")
                    cmd = ""
                    if name == "exec_command":
                        try:
                            a = json.loads(args_str)
                            cmd = a.get("cmd", "")
                        except (json.JSONDecodeError, TypeError):
                            pass
                    func_calls[i] = {"name": name, "cmd": cmd}
                elif pt == "function_call_output":
                    output = str(obj["payload"].get("output", ""))
                    func_outputs[i] = output
                elif pt == "custom_tool_call":
                    name = obj["payload"].get("name", "")
                    patch_calls[i] = {"name": name}
                elif pt == "custom_tool_call_output":
                    output = str(obj["payload"].get("output", ""))
                    patch_outputs[i] = output

        # Now process token_count events
        for i, obj in enumerate(events):
            if obj["type"] != "event_msg":
                continue
            payload = obj.get("payload", {})
            if payload.get("type") != "token_count":
                continue
            info = payload.get("info")
            if info is None:
                continue

            total = info["total_token_usage"]["total_tokens"]
            if total in seen_totals:
                continue
            seen_totals.add(total)

            lu = info["last_token_usage"]

            # Find the preceding function_call or custom_tool_call
            tool_name = ""
            cmd = ""
            patch_target = ""
            for j in range(i - 1, max(i - 6, -1), -1):
                if j in func_calls:
                    tool_name = func_calls[j]["name"]
                    cmd = func_calls[j]["cmd"]
                    break
                if j in patch_calls:
                    tool_name = patch_calls[j]["name"]
                    break

            # Find the following function_call_output or custom_tool_call_output
            output_text = ""
            for j in range(i + 1, min(i + 6, len(events))):
                if j in func_outputs:
                    output_text = func_outputs[j]
                    break
                if j in patch_outputs:
                    output_text = patch_outputs[j]
                    break

            # For apply_patch, find preceding output to get target files
            if tool_name == "apply_patch":
                # Look for the custom_tool_call_output after this token_count
                for j in range(i + 1, min(i + 6, len(events))):
                    if j in patch_outputs:
                        patch_out = patch_outputs[j]
                        patch_target = self._extract_patch_target(patch_out)
                        output_text = patch_out
                        break

            # Update error state from previous turn's output
            # (output_text here is from the CURRENT turn's result, but we need
            # the previous turn's result to set error state for THIS turn)
            # We'll track error state based on the output AFTER each turn

            # Extract coverage from output
            cov = self._extract_coverage(output_text, cmd)
            if cov is not None:
                latest_coverage = cov

            turns.append(
                {
                    "input_tokens": lu.get("input_tokens", 0),
                    "output_tokens": lu.get("output_tokens", 0),
                    "reasoning_tokens": lu.get("reasoning_output_tokens", 0),
                    "cached_input_tokens": lu.get("cached_input_tokens", 0),
                    "total_tokens": lu.get("total_tokens", 0),
                    "tool_name": tool_name,
                    "cmd": cmd,
                    "patch_target": patch_target,
                    "output_text": output_text,
                    "in_error_state": error_state,
                    "coverage_pct": latest_coverage,
                }
            )

            # Update error state AFTER recording this turn
            error_state = self._update_error_state(
                error_state, tool_name, cmd, output_text
            )

        return turns

    def _update_error_state(
        self, current_state: bool, tool_name: str, cmd: str, output: str
    ) -> bool:
        """Update error state based on tool output.

        Enter error state: vlog/vsim with non-zero exit, or apply_patch failure.
        Exit error state: vlog/vsim with exit code 0 (successful compile/sim).
        Environment issues (command not found, module load) do NOT trigger error state.
        """
        # Check for apply_patch failure/success
        if tool_name == "apply_patch":
            if "verification failed" in output.lower():
                return True
            # Successful apply_patch clears error state
            if "success" in output.lower():
                return False

        # Only actual vlog/vsim compile/sim commands affect error state
        # (not environment probes like 'which vlog', 'vlog -version', 'vlog -help')
        if tool_name == "exec_command":
            is_compile = "vlog " in cmd or "vlog\n" in cmd or cmd.strip().endswith("vlog")
            is_sim = "vsim " in cmd or "vsim\n" in cmd or cmd.strip().endswith("vsim")

            # Exclude environment probes and help commands
            env_probe = any(
                p in cmd
                for p in (
                    "which vlog", "which vsim",
                    "command -v vlog", "command -v vsim",
                    "vlog -version", "vsim -version",
                    "vlog -help", "vsim -help",
                )
            )

            if (is_compile or is_sim) and not env_probe:
                exit_code = self._parse_exit_code(output)
                if exit_code is not None:
                    # Exit code 127 = command not found (env setup, not code error)
                    if exit_code == 127:
                        return current_state
                    if exit_code > 0:
                        return True  # Enter error state
                    else:
                        return False  # Clear error state

        return current_state

    @staticmethod
    def _parse_exit_code(output: str) -> Optional[int]:
        """Parse exit code from exec_command output.

        Codex format: 'Process exited with code N'
        """
        m = re.search(r"Process exited with code (\d+)", output)
        if m:
            return int(m.group(1))
        # Fallback: bare 'exit code N'
        m = re.search(r"exit code (\d+)", output)
        if m:
            return int(m.group(1))
        return None

    @staticmethod
    def _extract_patch_target(output: str) -> str:
        """Extract target file path from apply_patch output."""
        try:
            data = json.loads(output)
            out_text = data.get("output", "")
        except (json.JSONDecodeError, TypeError):
            out_text = output

        # Look for file paths like "A work/codex_runs/trng_top/tb_llm_1.sv"
        # or "M work/codex_runs/ethmac_eth_with_cop/tb_llm_iter1.sv"
        m = re.search(r"[AM]\s+(\S+\.(?:sv|md))", out_text)
        if m:
            return m.group(1)
        return ""

    @staticmethod
    def _extract_coverage(output: str, cmd: str) -> Optional[float]:
        """Best-effort coverage extraction from vcover report output."""
        if "vcover report" not in cmd and "stmt_below_100" not in cmd:
            return None

        # Look for statement coverage summary patterns
        # Example: "Stmts    1234   1200   97.24%"
        m = re.search(r"Stmts\s+\d+\s+\d+\s+([\d.]+)%", output)
        if m:
            return float(m.group(1))

        # Look for "Total Coverage" or similar
        m = re.search(r"Total\s+.*?([\d.]+)%", output)
        if m:
            return float(m.group(1))

        return None

    def _classify_input(self, turn_idx: int) -> Category:
        """Classify input tokens based on previous turn's tool results."""
        if turn_idx == 0:
            return Category.SYSTEM_PROMPT

        prev = self.turns[turn_idx - 1]

        # D: Previous turn was in error state
        if prev.in_error_state:
            return Category.ERROR_RECOVERY

        # C: Previous turn ran vcover report or read coverage output
        if self._is_coverage_cmd(prev.cmd):
            return Category.COVERAGE_FEEDBACK

        # A: Previous turn read design/spec/RTL files
        if prev.tool_name == "exec_command" and self._is_design_cmd(prev.cmd):
            return Category.DESIGN_COMPREHENSION

        # B: Previous turn was apply_patch creating testbench
        if prev.tool_name == "apply_patch" and self._is_testbench_patch(
            prev.patch_target
        ):
            return Category.STIMULUS_GENERATION

        return Category.AGENTIC_OVERHEAD

    def _classify_output(self, turn: TurnRecord) -> Category:
        """Classify output tokens based on this turn's actions."""
        # D: Error state active
        if turn.in_error_state:
            return Category.ERROR_RECOVERY

        # B: apply_patch creating/modifying testbench
        if turn.tool_name == "apply_patch" and self._is_testbench_patch(
            turn.patch_target
        ):
            return Category.STIMULUS_GENERATION

        # A: Reading design/spec/RTL
        if turn.tool_name == "exec_command" and self._is_design_cmd(turn.cmd):
            return Category.DESIGN_COMPREHENSION

        # C: Running vcover report or reading coverage output
        if turn.tool_name == "exec_command" and self._is_coverage_cmd(turn.cmd):
            return Category.COVERAGE_FEEDBACK

        return Category.AGENTIC_OVERHEAD

    @staticmethod
    def _is_design_cmd(cmd: str) -> bool:
        """Check if exec_command reads design/spec/RTL files.

        Only matches file-reading commands (sed, cat, nl, rg, head, tail),
        not compile commands (vlog) that happen to reference design paths.
        """
        if not any(p in cmd for p in DESIGN_PATH_PATTERNS):
            return False
        # Exclude compile/sim commands that reference design files as arguments
        cmd_stripped = cmd.strip()
        # Multi-line commands: check the first significant line
        first_line = cmd_stripped.split("\n")[0].strip()
        for prefix in ("vlog", "vsim", "vcover", "vlib", "export ", "mkdir"):
            if first_line.startswith(prefix):
                return False
        # bash -lc wrapping: check for compile commands inside
        if "bash -lc" in cmd:
            if "vlog " in cmd or "vsim " in cmd or "vcover " in cmd:
                return False
        return True

    @staticmethod
    def _is_coverage_cmd(cmd: str) -> bool:
        """Check if exec_command runs or reads coverage reports."""
        if "vcover report" in cmd:
            return True
        if "stmt_below_100" in cmd:
            return True
        return False

    @staticmethod
    def _is_testbench_patch(patch_target: str) -> bool:
        """Check if apply_patch targets a testbench file (not report)."""
        if not patch_target:
            return False
        if patch_target.endswith(".sv") and "report" not in patch_target.lower():
            return True
        return False

    def build_result(self) -> CodexResult:
        """Build analysis result from parsed turns."""
        self.parse()

        result = CodexResult(
            design=self._meta.get("design", ""),
            model=self._meta.get("model", "unknown"),
            log_path=str(self.log_path),
            duration_seconds=self._meta.get("duration_seconds", 0.0),
            total_turns=len(self.turns),
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

            # Final coverage = last non-zero coverage
            for t in reversed(self.turns):
                if t.coverage_pct > 0:
                    result.final_coverage = t.coverage_pct
                    break

        result.by_category = self._compute_category_breakdown()
        result.per_turn = self._build_per_turn()
        result.coverage_curve = self._build_coverage_curve()

        return result

    def _compute_category_breakdown(self) -> Dict[str, Dict]:
        """Compute per-category aggregation with split input/output."""
        final_ctx = self.turns[-1].total_tokens if self.turns else 1
        breakdown = {}

        for cat in Category:
            in_turns = [t for t in self.turns if t.input_category == cat]
            cat_input = sum(t.new_input_tokens for t in in_turns)

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
        """Build per-turn breakdown."""
        rows = []
        for t in self.turns:
            tool_label = t.tool_name
            if t.cmd:
                tool_label = t.cmd[:80]
            elif t.patch_target:
                tool_label = f"apply_patch -> {t.patch_target}"
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
                    "coverage_pct": t.coverage_pct,
                    "in_error_state": t.in_error_state,
                    "tool": tool_label,
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


def _ascii_safe(s: str) -> str:
    """Replace non-ASCII characters for safe console output."""
    return s.encode("ascii", errors="replace").decode("ascii")


def print_per_turn_table(turns: List[TurnRecord]) -> None:
    """Print per-turn breakdown."""
    print(
        f"\n{'Turn':>5} | {'Cached':>7} | {'In (new)':>14} | "
        f"{'Out':>12} | {'Reasoning':>13} | {'Total (accum.)':>15} | Tool"
    )
    print(
        f"{'-' * 5}-+-{'-' * 7}-+-{'-' * 14}-+-{'-' * 12}-+-"
        f"{'-' * 13}-+-{'-' * 15}-+------"
    )

    for t in turns:
        in_label = f"{t.new_input_tokens:,} ({t.input_category.value})"
        out_label = f"{t.output_tokens:,} ({t.output_category.value})"
        rsn_label = f"{t.reasoning_tokens:,} ({t.output_category.value})"
        tool_label = t.tool_name
        if t.cmd:
            tool_label = _ascii_safe(t.cmd[:60])
        elif t.patch_target:
            tool_label = f"apply_patch -> {t.patch_target}"
        err_flag = " [ERR]" if t.in_error_state else ""
        print(
            f"{t.turn:>5} | {t.cached_input_tokens:>7,} | {in_label:>14} | "
            f"{out_label:>12} | {rsn_label:>13} | {t.total_tokens:>15,} | "
            f"{tool_label}{err_flag}"
        )
    print()


def print_category_summary(result: CodexResult) -> None:
    """Print per-category summary table."""
    print(f"\nDesign:    {result.design}")
    print(f"Model:     {result.model}")
    print(f"Coverage:  {result.final_coverage:.1f}%")
    print(f"Turns:     {result.total_turns}")
    print(f"Duration:  {format_duration(result.duration_seconds)}")
    print(f"Final Ctx: {result.final_context_tokens:,} tokens")

    t = result.to_dict()["tokens"]
    print(f"\nToken Totals:")
    print(f"  Input:     {t['input']:>10,}")
    print(f"  Output:    {t['output']:>10,}")
    print(f"  Reasoning: {t['reasoning']:>10,}")
    print(f"  Cached:    {t['cached_input']:>10,}")
    print(f"  Cache Hit: {t['cache_hit_rate'] * 100:>9.1f}%")

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
            f"{c.get('input_tokens', 0):>8,} "
            f"{c.get('visible_output_tokens', 0):>8,} "
            f"{c.get('reasoning_tokens', 0):>8,} "
            f"{c.get('total_output_tokens', 0):>8,} "
            f"{c.get('pct_of_final_context', 0) * 100:>6.1f}% "
            f"{c.get('num_turns_input', 0):>4} "
            f"{c.get('num_turns_output', 0):>4}"
        )

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
        f"{total_in:>8,} "
        f"{total_vis:>8,} "
        f"{total_rsn:>8,} "
        f"{total_out:>8,} "
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
        description="Codex CLI Compute Analysis: split input/output token categorization.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s codex_logs/trng_top.jsonl
  %(prog)s codex_logs/trng_top.jsonl --no-json
  %(prog)s codex_logs/ethmac_eth_with_cop.jsonl -o results/
        """,
    )
    parser.add_argument("log_path", help="Path to Codex .jsonl log")
    parser.add_argument(
        "-o", "--output-dir", default=".", help="Directory for output JSON"
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Suppress JSON output, only print console tables",
    )
    parser.add_argument(
        "--per-turn",
        action="store_true",
        help="Print per-turn table",
    )

    args = parser.parse_args()

    p = CodexParser(args.log_path)
    result = p.build_result()

    if args.per_turn:
        print_per_turn_table(p.turns)

    print_category_summary(result)

    if not args.no_json:
        out_name = f"{result.design}_codex_compute.json"
        if not result.design:
            out_name = f"{Path(args.log_path).stem}_codex_compute.json"
        out_path = Path(args.output_dir) / out_name
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"Wrote {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
