#!/usr/bin/env python3
"""Compute Study: Parse CovAgent/Codex logs into unified compute analysis.

Parses structured JSONL logs from either the CovAgent (ReAct/LangGraph) framework or
Codex CLI and produces a unified JSON summary showing where inference-time
tokens are spent across four activity categories:
  - Design Comprehension (reading spec/RTL)
  - Stimulus Generation (writing testbenches)
  - Error Recovery (fixing compile/sim failures)
  - Execution & Analysis (compile, sim, coverage, reporting)

Usage:
    python scripts/compute_study.py react work/EVALS/chacha_top/events.jsonl
    python scripts/compute_study.py codex "Codex Logs/chacha_top.jsonl"
    python scripts/compute_study.py compare result1.json result2.json ...
"""

import argparse
import json
import re
import sys
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import tiktoken


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------

_tiktoken_enc = None


def _get_encoder():
    global _tiktoken_enc
    if _tiktoken_enc is None:
        _tiktoken_enc = tiktoken.encoding_for_model("gpt-4o")
    return _tiktoken_enc


def count_tokens(text: str) -> int:
    """Count tokens in a string using the gpt-4o tokenizer."""
    return len(_get_encoder().encode(text)) if text else 0


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DESIGN_PATH_PATTERNS = ["spec/", "design/", "design_context/", "rtl/"]

CODEX_DESIGN_READ_PREFIXES = ["sed -n", "cat ", "nl -ba", "rg "]
CODEX_DESIGN_PATH_RES = [
    re.compile(r"data/[^/]*/spec/"),
    re.compile(r"data/[^/]*/design/"),
    re.compile(r"data/[^/]*/design_context/"),
    re.compile(r"data/[^/]*/rtl/"),
    re.compile(r"spec\.md"),
]
CODEX_ENV_PROBE_PATTERNS = ["module avail", "which vlog", "write_stdin", "module load"]

CODEX_COVERAGE_RE = re.compile(
    r"(?:Total|Stmts|Statement)\s*(?:coverage)?[^:\d]*:\s*(\d+\.?\d*)%", re.IGNORECASE
)
CODEX_EXIT_CODE_RE = re.compile(r"Process exited with code (\d+)")
CODEX_ERRORS_RE = re.compile(r"Errors:\s*(\d+)")


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------


class Category(str, Enum):
    DESIGN_COMPREHENSION = "design_comprehension"
    STIMULUS_GENERATION = "stimulus_generation"
    ERROR_RECOVERY = "error_recovery"
    EXECUTION_ANALYSIS = "execution_analysis"


@dataclass
class APICallRecord:
    """Internal per-API-call record used during parsing."""

    api_call: int
    iteration: int = 1
    category: Category = Category.EXECUTION_ANALYSIS
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cached_input_tokens: int = 0
    total_tokens: int = 0
    coverage_pct: float = 0.0
    tool_calls: List[str] = field(default_factory=list)
    tool_args: List[Dict] = field(default_factory=list)
    tool_result_tokens: int = 0  # tiktoken-counted tokens from tool results this call produced
    consecutive_failures: int = 0
    is_finalizing: bool = False


@dataclass
class ComputeStudyResult:
    """Unified output schema — both parsers produce this."""

    framework: str = ""
    design: str = ""
    model: str = ""
    log_path: str = ""
    duration_seconds: float = 0.0
    final_coverage: float = 0.0
    total_api_calls: int = 0
    total_iterations: int = 0
    tokens: Dict[str, Any] = field(default_factory=dict)
    by_category: Dict[str, Dict] = field(default_factory=dict)
    coverage_curve: List[Dict] = field(default_factory=list)
    per_iteration: List[Dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "framework": self.framework,
            "design": self.design,
            "model": self.model,
            "log_path": self.log_path,
            "duration_seconds": round(self.duration_seconds, 2),
            "final_coverage": round(self.final_coverage, 2),
            "total_api_calls": self.total_api_calls,
            "total_iterations": self.total_iterations,
            "tokens": self.tokens,
            "by_category": self.by_category,
            "coverage_curve": self.coverage_curve,
            "per_iteration": self.per_iteration,
        }


# ---------------------------------------------------------------------------
# LogParser ABC — shared aggregation logic
# ---------------------------------------------------------------------------


class LogParser(ABC):
    """Base class for log parsers."""

    def __init__(self, log_path: str):
        self.log_path = Path(log_path)
        self.records: List[APICallRecord] = []

    @abstractmethod
    def parse(self) -> None:
        """Parse the log file and populate self.records."""
        ...

    @abstractmethod
    def extract_metadata(self) -> Dict[str, Any]:
        """Return framework, design, model, duration_seconds, final_coverage, total_iterations."""
        ...

    def build_result(self) -> ComputeStudyResult:
        """Build unified ComputeStudyResult from parsed records + metadata."""
        self.parse()
        meta = self.extract_metadata()
        result = ComputeStudyResult(
            framework=meta["framework"],
            design=meta["design"],
            model=meta["model"],
            log_path=str(self.log_path),
            duration_seconds=meta["duration_seconds"],
            final_coverage=meta["final_coverage"],
            total_api_calls=len(self.records),
            total_iterations=meta["total_iterations"],
        )
        result.tokens = self._compute_token_totals()
        result.by_category = self._compute_category_breakdown()
        result.coverage_curve = self._build_coverage_curve()
        result.per_iteration = self._build_per_iteration()
        return result

    # -- Shared aggregation methods --

    def _compute_token_totals(self) -> Dict[str, Any]:
        inp = sum(r.input_tokens for r in self.records)
        out = sum(r.output_tokens for r in self.records)
        rsn = sum(r.reasoning_tokens for r in self.records)
        cached = sum(r.cached_input_tokens for r in self.records)
        tool_res = sum(r.tool_result_tokens for r in self.records)
        return {
            "input": inp,
            "output": out,
            "reasoning": rsn,
            "cached_input": cached,
            "tool_result": tool_res,
            "system_prompt": self._meta.get("system_prompt_tokens", 0),
            "cache_hit_rate": round(cached / inp, 4) if inp > 0 else 0.0,
        }

    def _compute_category_breakdown(self) -> Dict[str, Dict]:
        total_out = sum(r.output_tokens for r in self.records) or 1
        total_rsn = sum(r.reasoning_tokens for r in self.records)
        total_tr = sum(r.tool_result_tokens for r in self.records)
        grand_total = total_out + total_tr or 1  # reasoning already included in output
        total_calls = len(self.records) or 1
        result = {}
        for cat in Category:
            recs = [r for r in self.records if r.category == cat]
            cat_out = sum(r.output_tokens for r in recs)
            cat_rsn = sum(r.reasoning_tokens for r in recs)
            cat_tr = sum(r.tool_result_tokens for r in recs)
            cat_total = cat_out + cat_tr  # reasoning already included in output
            result[cat.value] = {
                "api_calls": len(recs),
                "output_tokens": cat_out,
                "visible_tokens": cat_out - cat_rsn,
                "reasoning_tokens": cat_rsn,
                "tool_result_tokens": cat_tr,
                "total_tokens": cat_total,
                "pct_output": round(cat_out / total_out, 4),
                "pct_total": round(cat_total / grand_total, 4),
                "pct_api_calls": round(len(recs) / total_calls, 4),
            }
        return result

    def _build_coverage_curve(self) -> List[Dict]:
        curve = []
        cum_out = 0
        for r in self.records:
            cum_out += r.output_tokens
            curve.append(
                {
                    "api_call": r.api_call,
                    "cumulative_output_tokens": cum_out,
                    "coverage_pct": r.coverage_pct,
                }
            )
        return curve

    def _build_per_iteration(self) -> List[Dict]:
        iters: Dict[int, Dict] = defaultdict(
            lambda: {
                "coverage_after": 0.0,
                "categories": {
                    c.value: {
                        "output_tokens": 0,
                        "reasoning_tokens": 0,
                        "tool_result_tokens": 0,
                        "api_calls": 0,
                    }
                    for c in Category
                },
            }
        )
        for r in self.records:
            it = iters[r.iteration]
            it["coverage_after"] = max(it["coverage_after"], r.coverage_pct)
            cat = it["categories"][r.category.value]
            cat["output_tokens"] += r.output_tokens
            cat["reasoning_tokens"] += r.reasoning_tokens
            cat["tool_result_tokens"] += r.tool_result_tokens
            cat["api_calls"] += 1
        return [{"iteration": i, **data} for i, data in sorted(iters.items())]


# ---------------------------------------------------------------------------
# ReActParser — events.jsonl
# ---------------------------------------------------------------------------


class ReActParser(LogParser):
    """Parser for ReAct framework events.jsonl files."""

    def __init__(self, log_path: str):
        super().__init__(log_path)
        self._meta: Dict[str, Any] = {}

    def parse(self) -> None:
        api_calls: Dict[int, Dict[str, Any]] = {}
        # Map call_id -> api_call number (from tool_call events)
        call_id_to_api: Dict[str, int] = {}
        # Collect tool results: call_id -> content string
        tool_results: List[tuple] = []  # (call_id, content)
        current_failures = 0
        current_iteration = 1
        current_coverage = 0.0
        is_finalizing = False

        with open(self.log_path) as f:
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
                        "framework": "covagent",
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
                            "tool_result_tokens": 0,
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
                            "tool_result_tokens": 0,
                        }
                    api_calls[ac]["tool_calls"].append(data["tool_name"])
                    api_calls[ac]["tool_args"].append(data.get("arguments", {}))
                    # Map call_id to api_call for tool_result matching
                    cid = data.get("call_id")
                    if cid:
                        call_id_to_api[cid] = ac

                elif event == "tool_result":
                    cid = data.get("call_id")
                    content = data.get("content", "")
                    tool_results.append((cid, content))

                elif event == "token_count":
                    ac = data["api_call"]
                    usage = data.get("last_usage", {})
                    if ac not in api_calls:
                        api_calls[ac] = {
                            "api_call": ac,
                            "tool_calls": [],
                            "tool_args": [],
                            "tool_result_tokens": 0,
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

        # Count tool result tokens and attribute to the API call that caused them
        for cid, content in tool_results:
            ac = call_id_to_api.get(cid)
            if ac is not None and ac in api_calls:
                api_calls[ac]["tool_result_tokens"] += count_tokens(
                    content if isinstance(content, str) else json.dumps(content)
                )

        # Convert to APICallRecord objects and classify
        for ac_num in sorted(api_calls.keys()):
            d = api_calls[ac_num]
            rec = APICallRecord(
                api_call=d["api_call"],
                iteration=d.get("iteration", 1),
                input_tokens=d.get("input_tokens", 0),
                output_tokens=d.get("output_tokens", 0),
                reasoning_tokens=d.get("reasoning_tokens", 0),
                cached_input_tokens=d.get("cached_input_tokens", 0),
                total_tokens=d.get("total_tokens", 0),
                coverage_pct=d.get("coverage_pct", 0.0),
                tool_calls=d.get("tool_calls", []),
                tool_args=d.get("tool_args", []),
                tool_result_tokens=d.get("tool_result_tokens", 0),
                consecutive_failures=d.get("consecutive_failures", 0),
                is_finalizing=d.get("is_finalizing", False),
            )
            rec.category = self._classify(rec)
            self.records.append(rec)

        # Store system prompt tokens (first API call's total input = prompt baseline)
        if self.records:
            self._meta["system_prompt_tokens"] = self.records[0].input_tokens

    def extract_metadata(self) -> Dict[str, Any]:
        if "total_iterations" not in self._meta and self.records:
            self._meta["total_iterations"] = max(r.iteration for r in self.records)
        if "final_coverage" not in self._meta and self.records:
            self._meta["final_coverage"] = max(r.coverage_pct for r in self.records)
        self._meta.setdefault("duration_seconds", 0)
        self._meta.setdefault("framework", "covagent")
        self._meta.setdefault("design", "")
        self._meta.setdefault("model", "unknown")
        return self._meta

    @staticmethod
    def _classify(rec: APICallRecord) -> Category:
        """Classify a ReAct API call. Priority order per COMPUTE_STUDY.md."""
        # Finalize override — report writing
        if rec.is_finalizing:
            return Category.EXECUTION_ANALYSIS

        # 1. Error Recovery (highest priority)
        if rec.consecutive_failures > 0:
            return Category.ERROR_RECOVERY

        # 2. Stimulus Generation
        for i, tool in enumerate(rec.tool_calls):
            if tool == "run_verification_cycle":
                return Category.STIMULUS_GENERATION
            if tool == "write_file" and i < len(rec.tool_args):
                path = str(
                    rec.tool_args[i].get("path", "")
                    or rec.tool_args[i].get("testbench_path", "")
                )
                if (
                    "testbenches/" in path
                    and path.endswith(".sv")
                    and "report" not in path.lower()
                ):
                    return Category.STIMULUS_GENERATION

        # 3. Design Comprehension
        for i, tool in enumerate(rec.tool_calls):
            if tool == "read_file" and i < len(rec.tool_args):
                path = str(rec.tool_args[i].get("path", ""))
                if any(p in path for p in DESIGN_PATH_PATTERNS):
                    return Category.DESIGN_COMPREHENSION

        # 4. Execution & Analysis (everything else)
        return Category.EXECUTION_ANALYSIS


# ---------------------------------------------------------------------------
# CodexParser — Codex CLI .jsonl
# ---------------------------------------------------------------------------


class CodexParser(LogParser):
    """Parser for Codex CLI .jsonl log files."""

    def __init__(self, log_path: str):
        super().__init__(log_path)
        self._meta: Dict[str, Any] = {}
        self._in_error_recovery = False

    def parse(self) -> None:
        events = []
        with open(self.log_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                events.append(json.loads(line))

        self._extract_meta_from_events(events)
        turns = self._segment_into_turns(events)

        prev_cumulative: Dict[str, int] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "reasoning_output_tokens": 0,
            "cached_input_tokens": 0,
            "total_tokens": 0,
        }

        api_call_num = 0
        current_iteration = 0  # will become 1 on first apply_patch or first tool call
        coverage = 0.0
        started = False

        for turn in turns:
            tool_calls = turn["tool_calls"]
            tool_outputs = turn["tool_outputs"]
            token_count = turn["token_count"]

            if not tool_calls and token_count is None:
                continue

            api_call_num += 1
            if not started:
                current_iteration = 1
                started = True

            # Compute per-turn token deltas
            if token_count:
                delta = {
                    "input_tokens": token_count.get("input_tokens", 0)
                    - prev_cumulative.get("input_tokens", 0),
                    "output_tokens": token_count.get("output_tokens", 0)
                    - prev_cumulative.get("output_tokens", 0),
                    "reasoning_tokens": token_count.get("reasoning_output_tokens", 0)
                    - prev_cumulative.get("reasoning_output_tokens", 0),
                    "cached_input_tokens": token_count.get("cached_input_tokens", 0)
                    - prev_cumulative.get("cached_input_tokens", 0),
                }
                delta["total_tokens"] = delta["input_tokens"] + delta["output_tokens"]
                prev_cumulative = dict(token_count)
            else:
                delta = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "reasoning_tokens": 0,
                    "cached_input_tokens": 0,
                    "total_tokens": 0,
                }

            # Check for iteration boundary: apply_patch creating .sv testbench
            for name, args, _ in tool_calls:
                if name == "apply_patch":
                    patch_text = args if isinstance(args, str) else ""
                    if (
                        ".sv" in patch_text
                        and "report" not in patch_text.lower()
                        and "thought" not in patch_text.lower()
                    ):
                        current_iteration += 1

            # Update error recovery state from tool outputs
            self._update_error_state(tool_calls, tool_outputs)

            # Classify this turn
            category = self._classify_turn(tool_calls, tool_outputs)

            # Extract coverage from vcover report outputs
            for _, output in tool_outputs:
                cov = self._extract_coverage(output)
                if cov is not None:
                    coverage = cov

            # Count tool result tokens (tiktoken) for this turn
            turn_tool_result_tokens = 0
            for _, output in tool_outputs:
                if isinstance(output, str):
                    turn_tool_result_tokens += count_tokens(output)

            rec = APICallRecord(
                api_call=api_call_num,
                iteration=max(1, current_iteration),
                category=category,
                input_tokens=max(0, delta["input_tokens"]),
                output_tokens=max(0, delta["output_tokens"]),
                reasoning_tokens=max(0, delta["reasoning_tokens"]),
                cached_input_tokens=max(0, delta["cached_input_tokens"]),
                total_tokens=max(0, delta["total_tokens"]),
                coverage_pct=coverage,
                tool_calls=[name for name, _, _ in tool_calls],
                tool_args=[
                    args if isinstance(args, dict) else {"raw": str(args)[:200]}
                    for _, args, _ in tool_calls
                ],
                tool_result_tokens=turn_tool_result_tokens,
                consecutive_failures=1 if self._in_error_recovery else 0,
            )
            self.records.append(rec)

        # Store system prompt tokens (first turn's input = prompt baseline)
        if self.records:
            self._meta["system_prompt_tokens"] = self.records[0].input_tokens

    def extract_metadata(self) -> Dict[str, Any]:
        if self.records:
            self._meta["total_iterations"] = max(r.iteration for r in self.records)
            # Use last record's coverage (not max) — instance-specific reports
            # can temporarily show higher coverage than the top-level summary.
            self._meta["final_coverage"] = self.records[-1].coverage_pct
        self._meta.setdefault("total_iterations", 0)
        self._meta.setdefault("final_coverage", 0.0)
        self._meta.setdefault("duration_seconds", 0.0)
        return self._meta

    # -- Internal helpers --

    def _extract_meta_from_events(self, events: List[Dict]) -> None:
        self._meta = {
            "framework": "codex",
            "design": self.log_path.stem,
            "model": "unknown",
            "duration_seconds": 0.0,
            "final_coverage": 0.0,
            "total_iterations": 0,
        }
        first_ts: Optional[str] = None
        last_ts: Optional[str] = None
        for evt in events:
            ts = evt.get("timestamp")
            if ts:
                if first_ts is None:
                    first_ts = ts
                last_ts = ts
            p = evt.get("payload", {})
            if evt.get("type") == "turn_context":
                if self._meta["model"] == "unknown":
                    self._meta["model"] = p.get("model", "unknown")
        if first_ts and last_ts:
            try:
                t0 = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                self._meta["duration_seconds"] = (t1 - t0).total_seconds()
            except (ValueError, TypeError):
                pass

    def _segment_into_turns(self, events: List[Dict]) -> List[Dict]:
        """Segment events into turns delimited by turn_context events."""
        turns: List[Dict] = []
        current: Dict[str, Any] = {
            "tool_calls": [],
            "tool_outputs": [],
            "token_count": None,
        }

        for evt in events:
            et = evt.get("type", "")
            p = evt.get("payload", {})

            if et == "turn_context":
                if current["tool_calls"] or current["token_count"]:
                    turns.append(current)
                current = {
                    "tool_calls": [],
                    "tool_outputs": [],
                    "token_count": None,
                }

            elif et == "response_item":
                pt = p.get("type", "")
                if pt == "function_call":
                    name = p.get("name", "")
                    raw_args = p.get("arguments", "{}")
                    try:
                        args = (
                            json.loads(raw_args)
                            if isinstance(raw_args, str)
                            else raw_args
                        )
                    except json.JSONDecodeError:
                        args = {"raw": raw_args}
                    current["tool_calls"].append(
                        (name, args, p.get("call_id", ""))
                    )
                elif pt == "custom_tool_call":
                    name = p.get("name", "")
                    patch_input = p.get("input", "")
                    current["tool_calls"].append(
                        (name, patch_input, p.get("call_id", ""))
                    )
                elif pt in ("function_call_output", "custom_tool_call_output"):
                    current["tool_outputs"].append(
                        (p.get("call_id", ""), p.get("output", ""))
                    )

            elif et == "event_msg" and p.get("type") == "token_count":
                info = p.get("info")
                if info and info.get("total_token_usage"):
                    current["token_count"] = info["total_token_usage"]

        # Final turn
        if current["tool_calls"] or current["token_count"]:
            turns.append(current)

        return turns

    def _update_error_state(
        self,
        tool_calls: List[tuple],
        tool_outputs: List[tuple],
    ) -> None:
        """Update error recovery state based on command exit codes."""
        call_id_to_cmd: Dict[str, str] = {}
        for name, args, cid in tool_calls:
            if name == "exec_command":
                cmd = args.get("cmd", "") if isinstance(args, dict) else ""
                call_id_to_cmd[cid] = cmd

        for cid, output in tool_outputs:
            cmd = call_id_to_cmd.get(cid, "")
            is_compile = "vlog" in cmd
            is_sim = "vsim" in cmd
            if not (is_compile or is_sim):
                continue

            exit_match = CODEX_EXIT_CODE_RE.search(output)
            if exit_match:
                code = int(exit_match.group(1))
                if code != 0:
                    self._in_error_recovery = True
                    continue

            err_match = CODEX_ERRORS_RE.search(output)
            if err_match and int(err_match.group(1)) > 0:
                self._in_error_recovery = True
                continue

            # Successful compile resets error recovery
            if is_compile:
                self._in_error_recovery = False

    def _classify_turn(
        self,
        tool_calls: List[tuple],
        tool_outputs: List[tuple],
    ) -> Category:
        """Classify a Codex turn. Priority order per COMPUTE_STUDY.md."""
        commands: List[str] = []
        has_apply_patch_sv = False

        for name, args, _ in tool_calls:
            if name == "exec_command":
                cmd = args.get("cmd", "") if isinstance(args, dict) else ""
                commands.append(cmd)
            elif name == "apply_patch":
                patch_text = args if isinstance(args, str) else ""
                if (
                    ".sv" in patch_text
                    and "report" not in patch_text.lower()
                    and "thought" not in patch_text.lower()
                ):
                    has_apply_patch_sv = True

        # 1. Error Recovery
        if self._in_error_recovery:
            return Category.ERROR_RECOVERY
        for cmd in commands:
            if any(p in cmd for p in CODEX_ENV_PROBE_PATTERNS):
                return Category.ERROR_RECOVERY

        # 2. Stimulus Generation
        if has_apply_patch_sv:
            return Category.STIMULUS_GENERATION

        # 3. Design Comprehension
        for cmd in commands:
            if any(prefix in cmd for prefix in CODEX_DESIGN_READ_PREFIXES):
                if any(pat.search(cmd) for pat in CODEX_DESIGN_PATH_RES):
                    return Category.DESIGN_COMPREHENSION

        # 4. Execution & Analysis
        return Category.EXECUTION_ANALYSIS

    @staticmethod
    def _extract_coverage(output: str) -> Optional[float]:
        """Extract coverage percentage from vcover report output.

        Uses the last match to prefer top-level summaries over instance-specific ones.
        """
        matches = CODEX_COVERAGE_RE.findall(output)
        return float(matches[-1]) if matches else None


# ---------------------------------------------------------------------------
# Comparison & Table Output
# ---------------------------------------------------------------------------


def format_duration(secs: float) -> str:
    if secs >= 3600:
        return f"{secs / 3600:.1f}h"
    elif secs >= 60:
        return f"{secs / 60:.1f}m"
    return f"{secs:.0f}s"


def print_single_summary(result: ComputeStudyResult) -> None:
    """Print a concise summary for a single parsed result."""
    t = result.tokens
    print(f"\nAgent: \t\t{result.framework.upper()}")
    print(f"Design: \t{result.design}")
    print(f"LLM: \t\t{result.model}")
    print(
        f"\nCoverage: \t{result.final_coverage:.1f}%"
        f"\nAPI Calls: \t{result.total_api_calls}  "
        f"\nIterations: \t{result.total_iterations}  "
        f"\nDuration: \t{format_duration(result.duration_seconds)}"
    )
    print(
        f"\nTokens:"
        f"\nIn: \t\t{t.get('input', 0):,}  "
        f"\nOut: \t\t{t.get('output', 0):,}  "
        f"\nReasoning: \t{t.get('reasoning', 0):,}  "
        f"\nCached: \t{t.get('cached_input', 0):,}  "
        f"\nCacheRate: \t{t.get('cache_hit_rate', 0) * 100:.1f}%"
    )
    print(
        f"\nTool Results: \t{t.get('tool_result', 0):,}  "
        f"\nSystem Prompt: \t{t.get('system_prompt', 0):,}"
    )
    print(
        f"\n  {'Category':<25} {'API#':>5} {'OutTok':>8} {'VisTok':>8} {'RsnTok':>8} "
        f"{'ToolRes':>8} {'Total':>8} {'%Total':>7} {'%API':>6}"
    )
    print(f"  {'-' * 91}")
    for cat_name in [c.value for c in Category]:
        c = result.by_category.get(cat_name, {})
        label = cat_name.replace("_", " ").title()
        print(
            f"  {label:<25} {c.get('api_calls', 0):>5} "
            f"{c.get('output_tokens', 0):>8,} "
            f"{c.get('visible_tokens', 0):>8,} "
            f"{c.get('reasoning_tokens', 0):>8,} "
            f"{c.get('tool_result_tokens', 0):>8,} "
            f"{c.get('total_tokens', 0):>8,} "
            f"{c.get('pct_total', 0) * 100:>6.1f}% "
            f"{c.get('pct_api_calls', 0) * 100:>5.1f}%"
        )
    print(f"{'=' * 99}\n")


def compare_results(results: List[ComputeStudyResult]) -> None:
    """Print comparison tables for multiple parsed results."""
    print(f"\n{'=' * 130}")
    print(
        f"{'Design':<25} {'Frmwk':<8} {'Model':<15} {'Cov%':>6} "
        f"{'API#':>5} {'Iter':>5} {'OutTok':>8} {'RsnTok':>8} "
        f"{'ToolRes':>8} {'Cache%':>7} {'Time':>7}"
    )
    print(f"{'-' * 130}")
    for r in results:
        t = r.tokens
        print(
            f"{r.design:<25} {r.framework:<8} {r.model:<15} "
            f"{r.final_coverage:>5.1f}% {r.total_api_calls:>5} "
            f"{r.total_iterations:>5} "
            f"{t.get('output', 0):>8,} {t.get('reasoning', 0):>8,} "
            f"{t.get('tool_result', 0):>8,} "
            f"{t.get('cache_hit_rate', 0) * 100:>6.1f}% "
            f"{format_duration(r.duration_seconds):>7}"
        )
    print(f"{'=' * 130}")

    print(f"\nCategory Breakdown (% of total caused tokens: output + reasoning + tool results):")
    print(
        f"{'Design':<25} {'Frmwk':<8} "
        f"{'Compreh':>9} {'Stimulus':>9} {'ErrRecov':>9} {'ExecAnly':>9}"
    )
    print(f"{'-' * 75}")
    for r in results:
        bc = r.by_category
        dc = bc.get("design_comprehension", {})
        sg = bc.get("stimulus_generation", {})
        er = bc.get("error_recovery", {})
        ea = bc.get("execution_analysis", {})
        print(
            f"{r.design:<25} {r.framework:<8} "
            f"{dc.get('pct_total', 0) * 100:>8.1f}% "
            f"{sg.get('pct_total', 0) * 100:>8.1f}% "
            f"{er.get('pct_total', 0) * 100:>8.1f}% "
            f"{ea.get('pct_total', 0) * 100:>8.1f}%"
        )
    print(f"{'=' * 75}\n")


def load_result_from_json(path: str) -> ComputeStudyResult:
    """Load a previously-saved ComputeStudyResult JSON file."""
    with open(path) as f:
        data = json.load(f)
    result = ComputeStudyResult()
    for key in [
        "framework",
        "design",
        "model",
        "log_path",
        "duration_seconds",
        "final_coverage",
        "total_api_calls",
        "total_iterations",
        "tokens",
        "by_category",
        "coverage_curve",
        "per_iteration",
    ]:
        if key in data:
            setattr(result, key, data[key])
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute Study: Parse CovAgent/Codex logs into unified analysis.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s react work/EVALS/chacha_top/events.jsonl
  %(prog)s codex "Codex Logs/chacha_top.jsonl"
  %(prog)s compare chacha_top_react_compute.json chacha_top_codex_compute.json
        """,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    react_p = subparsers.add_parser("react", help="Parse a CovAgent (ReAct) events.jsonl")
    react_p.add_argument("log_path", help="Path to events.jsonl")
    react_p.add_argument(
        "-o", "--output-dir", default=".", help="Directory for output JSON"
    )

    codex_p = subparsers.add_parser("codex", help="Parse a Codex .jsonl")
    codex_p.add_argument("log_path", help="Path to Codex session .jsonl")
    codex_p.add_argument(
        "-o", "--output-dir", default=".", help="Directory for output JSON"
    )

    cmp_p = subparsers.add_parser("compare", help="Compare parsed results")
    cmp_p.add_argument("files", nargs="+", help="Paths to *_compute.json files")

    args = parser.parse_args()

    if args.command in ("react", "codex"):
        if args.command == "react":
            p: LogParser = ReActParser(args.log_path)
        else:
            p = CodexParser(args.log_path)

        result = p.build_result()
        out_name = f"{result.design}_{result.framework}_compute.json"
        out_path = Path(args.output_dir) / out_name
        with open(out_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"Wrote {out_path}")
        print_single_summary(result)

    elif args.command == "compare":
        results = [load_result_from_json(f) for f in args.files]
        compare_results(results)

    return 0


if __name__ == "__main__":
    sys.exit(main())
