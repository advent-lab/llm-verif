"""Agent registry tool — read_agents (orchestrator's roster view)."""

from __future__ import annotations

from covagent.tools.types import ToolContext, ToolResult


def read_agents(
    ctx: ToolContext,
    status: str | None = None,
    feature: str | None = None,
) -> ToolResult:
    if not ctx.agents_ref:
        return {
            "ok": True,
            "data": [],
            "error": None,
            "summary": "no agents registered",
        }
    agents: dict = ctx.agents_ref[0]
    rows = list(agents.values())
    if status is not None:
        rows = [a for a in rows if a.get("status") == status]
    if feature is not None:
        rows = [a for a in rows if a.get("feature_label") == feature]
    return {
        "ok": True,
        "data": rows,
        "error": None,
        "summary": f"{len(rows)} agent(s){' status=' + status if status else ''}",
    }
