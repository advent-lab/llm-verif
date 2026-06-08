"""Coverage query tool — wraps simulator parse_coverage against the master DB."""

from __future__ import annotations

from covagent.logging.events import iso_now
from covagent.tools.types import ToolContext, ToolResult


def _err(summary: str, error: str) -> ToolResult:
    return {"ok": False, "data": None, "error": error, "summary": summary}


def _ok(data: object, summary: str) -> ToolResult:
    return {"ok": True, "data": data, "error": None, "summary": summary}


def query_coverage(ctx: ToolContext, scope: str = "*", mode: str | None = None) -> ToolResult:
    if ctx.simulator is None:
        return _err("query_coverage: no simulator", "ToolContext.simulator not set")
    if ctx.coverage_master is None or not ctx.coverage_master.exists():
        return _err(
            "query_coverage: no master DB",
            f"master DB not present at {ctx.coverage_master}",
        )
    cov_mode = mode or ctx.coverage_mode  # type: ignore[assignment]
    if cov_mode not in ("functional", "code"):
        return _err("query_coverage: bad mode", f"unknown mode '{cov_mode}'")
    summary = ctx.simulator.parse_coverage(ctx.coverage_master, cov_mode)  # type: ignore[arg-type]

    breakdown = summary.breakdown
    if scope != "*" and scope in breakdown:
        scope_pct = breakdown[scope]
    else:
        scope_pct = summary.overall_pct

    unhit = summary.unhit_items[: ctx.unhit_truncate]
    data = {
        "name": scope,
        "pct": scope_pct,
        "items_hit": summary.items_hit,
        "items_total": summary.items_total,
        "unhit_items": unhit,
        "snapshot_at": iso_now(),
        "mode": cov_mode,
        "breakdown": breakdown if scope == "*" else {scope: scope_pct},
    }
    return _ok(
        data,
        f"coverage[{scope}] = {scope_pct:.1f}% ({summary.items_hit}/{summary.items_total})",
    )
