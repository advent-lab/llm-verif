"""Shared coverage status tool for CovAgent v2 multi-agent architecture.

Provides a single tool with configurable detail levels that both the
Orchestrator and Design Expert can use to query coverage status.
The cache is updated by the parent graph's update_state_node after
each coverage merge.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from langchain.tools import tool
import logging


# Module-level cache, updated by update_state_node after each merge
_coverage_cache: Dict[str, Any] = {
    "cumulative_coverage": 0.0,
    "iteration": 0,
    "breakdown": {},            # {file_path: coverage_pct}
    "uncovered_lines": {},      # {file_path: [line_nums]}
    "annotated_source": "",     # Full annotated source (Tier 2)
    "compressed_summary": "",   # Compressed summary (Tier 1)
    "gen_results": [],          # Latest generator results
    "initialized": False,       # True after first coverage merge
    # Functional coverage fields (only populated when functional_coverage_enabled)
    "functional_coverage_enabled": False,
    "functional_coverage": 0.0,
    "uncovered_bins": [],       # Flat list of uncovered bin dicts
}


def update_coverage_cache(
    cumulative_coverage: float,
    iteration: int,
    breakdown: Dict[str, float],
    uncovered_lines: Dict[str, List[int]],
    annotated_source: str,
    gen_results: Optional[List[dict]] = None,
    prev_coverage: float = 0.0,
    functional_coverage_enabled: bool = False,
    functional_coverage: float = 0.0,
    uncovered_bins: Optional[List[dict]] = None,
) -> None:
    """Update the coverage cache after a coverage merge.

    Called by update_state_node in orc_exp_gen.py and ag_crt.py.
    """
    global _coverage_cache

    _coverage_cache["cumulative_coverage"] = cumulative_coverage
    _coverage_cache["iteration"] = iteration
    _coverage_cache["breakdown"] = breakdown
    _coverage_cache["uncovered_lines"] = uncovered_lines
    _coverage_cache["annotated_source"] = annotated_source
    _coverage_cache["gen_results"] = gen_results or []
    _coverage_cache["initialized"] = True
    _coverage_cache["functional_coverage_enabled"] = functional_coverage_enabled
    _coverage_cache["functional_coverage"] = functional_coverage
    _coverage_cache["uncovered_bins"] = uncovered_bins or []

    # Build compressed summary (Tier 1)
    _coverage_cache["compressed_summary"] = _build_compressed_summary(
        cumulative_coverage, prev_coverage, breakdown, uncovered_lines,
        gen_results or [], iteration,
        functional_coverage_enabled=functional_coverage_enabled,
        functional_coverage=functional_coverage,
        uncovered_bins=uncovered_bins or [],
    )


def _build_compressed_summary(
    new_cov: float,
    prev_cov: float,
    breakdown: Dict[str, float],
    uncovered_lines: Dict[str, List[int]],
    gen_results: List[dict],
    iteration: int,
    functional_coverage_enabled: bool = False,
    functional_coverage: float = 0.0,
    uncovered_bins: Optional[List[dict]] = None,
) -> str:
    """Build Tier 1 compressed coverage summary for the Orchestrator."""
    if functional_coverage_enabled:
        # Functional coverage mode: show only funcov metrics
        parts = [
            f"Functional Coverage: {functional_coverage:.2f}%",
            "",
        ]
        if uncovered_bins:
            parts.append(f"Uncovered bins ({len(uncovered_bins)} remaining):")
            for b in uncovered_bins[:10]:
                parts.append(
                    f"  - {b.get('covergroup','?')}.{b.get('coverpoint','?')}: `{b.get('bin_name','?')}`"
                )
            if len(uncovered_bins) > 10:
                parts.append(f"  ... (+{len(uncovered_bins)-10} more bins)")
            parts.append("")
    else:
        # Code coverage mode: show only code coverage metrics
        delta = new_cov - prev_cov
        parts = [
            f"Cumulative Coverage: {new_cov:.2f}%"
            f" (was {prev_cov:.2f}%, {'+' if delta >= 0 else ''}{delta:.2f}% this iteration)",
            "",
        ]

        # Uncovered lines by module
        if uncovered_lines:
            parts.append("Uncovered by module:")
            for file_path, lines in sorted(uncovered_lines.items()):
                filename = Path(file_path).name
                if not lines:
                    continue
                ranges = _group_line_ranges(lines)
                range_str = ", ".join(ranges[:5])
                if len(ranges) > 5:
                    range_str += f" ... (+{len(ranges) - 5} more regions)"
                parts.append(f"  {filename}: {len(lines)} lines ({range_str})")
            parts.append("")

        # Per-module coverage breakdown
        if breakdown:
            parts.append("Module coverage breakdown:")
            for file_path, cov in sorted(breakdown.items()):
                filename = Path(file_path).name
                parts.append(f"  {filename}: {cov:.1f}%")
            parts.append("")

    # Generator results this iteration (both modes)
    if gen_results:
        parts.append(f"Generators this iteration (iter {iteration}):")
        for r in gen_results:
            gen_id = r.get("gen_id", "?")
            target = r.get("target_module", "top")
            success = r.get("success", False)
            summary = r.get("summary", "")
            status = "SUCCESS" if success else "FAILED"
            short_summary = summary[:150] + "..." if len(summary) > 150 else summary
            parts.append(f"  gen_{gen_id} ({target}): {status} — {short_summary}")
        parts.append("")

    parts.append(f"No-progress count: (see framework state)")
    return "\n".join(parts)


def _build_module_breakdown(
    breakdown: Dict[str, float],
    uncovered_lines: Dict[str, List[int]],
) -> str:
    """Build per-module breakdown with line ranges."""
    if not uncovered_lines and not breakdown:
        return "No coverage data available yet."

    parts = []
    for file_path in sorted(set(list(breakdown.keys()) + list(uncovered_lines.keys()))):
        filename = Path(file_path).name
        cov = breakdown.get(file_path, 0.0)
        lines = uncovered_lines.get(file_path, [])
        parts.append(f"## {filename} — {cov:.1f}% covered")
        if lines:
            ranges = _group_line_ranges(lines)
            parts.append(f"Uncovered regions ({len(lines)} lines):")
            for r in ranges:
                parts.append(f"  - Lines {r}")
        else:
            parts.append("  Fully covered")
        parts.append("")

    return "\n".join(parts)


def _group_line_ranges(lines: List[int]) -> List[str]:
    """Group sorted line numbers into ranges like '100-105', '200'."""
    if not lines:
        return []
    sorted_lines = sorted(set(lines))
    ranges = []
    start = sorted_lines[0]
    end = sorted_lines[0]

    for line in sorted_lines[1:]:
        if line == end + 1:
            end = line
        else:
            ranges.append(f"{start}-{end}" if start != end else str(start))
            start = end = line
    ranges.append(f"{start}-{end}" if start != end else str(start))
    return ranges


@tool
def get_coverage_status(detail_level: str = "summary") -> str:
    """Get the current cumulative coverage status.

    Args:
        detail_level: Level of detail to return:
            - "summary": Coverage %, hole counts per module, generator results.
              Best for strategic decision-making (Orchestrator).
            - "detailed": Full annotated source with every uncovered line marked
              in context. Best for deep hole analysis (Design Expert).
            - "module": Per-module breakdown with uncovered line ranges.
              Useful for targeting specific modules.

    Returns:
        Coverage status at the requested detail level.
    """
    if not _coverage_cache["initialized"]:
        return (
            "No coverage data available yet. "
            "Coverage status becomes available after the first successful "
            "test generator dispatch and coverage merge."
        )

    if detail_level == "summary":
        return _coverage_cache["compressed_summary"]
    elif detail_level == "detailed":
        if _coverage_cache.get("functional_coverage_enabled"):
            func_cov = _coverage_cache.get("functional_coverage", 0.0)
            bins = _coverage_cache.get("uncovered_bins", [])
            if not bins:
                return f"Functional coverage: {func_cov:.2f}%. All bins covered."
            lines = [f"Functional coverage: {func_cov:.2f}% ({len(bins)} bins uncovered)\n"]
            for b in bins:
                cg = b.get('covergroup', '?')
                cp = b.get('coverpoint', '?')
                bn = b.get('bin_name', '?')
                kind = b.get('coverpoint_kind', '')
                kind_str = f" [{kind}]" if kind else ""
                lines.append(f"  - {cg}.{cp}{kind_str}: `{bn}`")
            return "\n".join(lines)
        source = _coverage_cache["annotated_source"]
        if not source:
            return (
                f"Cumulative coverage: {_coverage_cache['cumulative_coverage']:.2f}%. "
                "No annotated source available (all lines may be covered)."
            )
        return (
            f"Cumulative coverage: {_coverage_cache['cumulative_coverage']:.2f}%\n\n"
            f"{source}"
        )
    elif detail_level == "module":
        return _build_module_breakdown(
            _coverage_cache["breakdown"],
            _coverage_cache["uncovered_lines"],
        )
    else:
        return (
            f"Unknown detail_level: '{detail_level}'. "
            "Use 'summary', 'detailed', or 'module'."
        )
