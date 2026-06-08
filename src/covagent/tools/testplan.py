"""Testplan tools — read_testplan, patch_testplan, append_history, etc.

State-mutating tools work through `ctx.testplan_ref` (a single-element list
acting as a mutable holder). The orchestrate / update_state nodes set the
ref, run the LLM turn (which may invoke patch_testplan / append_history),
then read the mutated plan back out.
"""

from __future__ import annotations

from typing import Literal

from covagent.logging.events import iso_now
from covagent.state.testplan import (
    CodeScope,
    Covergroup,
    HistoryEntry,
    Testplan,
    Testpoint,
)
from covagent.tools.types import ToolContext, ToolResult

TargetType = Literal["testpoint", "covergroup", "code_scope"]


def _err(summary: str, error: str) -> ToolResult:
    return {"ok": False, "data": None, "error": error, "summary": summary}


def _ok(data: object, summary: str) -> ToolResult:
    return {"ok": True, "data": data, "error": None, "summary": summary}


def _plan(ctx: ToolContext) -> Testplan | None:
    return ctx.testplan_ref[0] if ctx.testplan_ref else None


def _items(plan: Testplan, target_type: TargetType) -> list:
    if target_type == "testpoint":
        return plan.testpoints
    if target_type == "covergroup":
        return plan.covergroups
    if target_type == "code_scope":
        return plan.code_scopes
    raise ValueError(f"unknown target_type {target_type!r}")


def _find(plan: Testplan, target_type: TargetType, name: str):
    for item in _items(plan, target_type):
        if item.name == name:
            return item
    return None


def read_testplan(
    ctx: ToolContext,
    target_type: TargetType | None = None,
    name: str | None = None,
    status: str | None = None,
) -> ToolResult:
    plan = _plan(ctx)
    if plan is None:
        return _err("read_testplan: no plan", "ToolContext.testplan_ref empty")

    if name is not None:
        if target_type is None:
            return _err("read_testplan: name without target_type", "specify target_type")
        item = _find(plan, target_type, name)
        if item is None:
            return _err("read_testplan: not found", f"no {target_type} named {name!r}")
        return _ok(item.model_dump(), f"{target_type}/{name}")

    def _filter(items: list) -> list:
        return [i.model_dump() for i in items if status is None or i.status == status]

    if target_type is not None:
        items = _filter(_items(plan, target_type))
        return _ok(items, f"{len(items)} {target_type}(s)")

    data = {
        "mode": plan.mode,
        "testpoints": _filter(plan.testpoints),
        "covergroups": _filter(plan.covergroups),
        "code_scopes": _filter(plan.code_scopes),
    }
    return _ok(
        data,
        f"plan: {len(plan.testpoints)} tp, {len(plan.covergroups)} cg, {len(plan.code_scopes)} cs",
    )


def read_summary(ctx: ToolContext) -> ToolResult:
    plan = _plan(ctx)
    if plan is None:
        return _err("read_summary: no plan", "ToolContext.testplan_ref empty")

    def _stats(items: list) -> dict:
        n = len(items)
        out = {"total": n}
        for s in ("todo", "incomplete", "complete", "blocked"):
            out[s] = sum(1 for i in items if i.status == s)
        return out

    data = {
        "mode": plan.mode,
        "testpoints": _stats(plan.testpoints),
        "covergroups": _stats(plan.covergroups),
        "code_scopes": _stats(plan.code_scopes),
    }
    return _ok(data, f"plan summary in mode={plan.mode}")


def read_history(
    ctx: ToolContext, target_type: TargetType, name: str
) -> ToolResult:
    plan = _plan(ctx)
    if plan is None:
        return _err("read_history: no plan", "ToolContext.testplan_ref empty")
    item = _find(plan, target_type, name)
    if item is None:
        return _err("read_history: not found", f"no {target_type} named {name!r}")
    return _ok(
        [h.model_dump() for h in item.history],
        f"{len(item.history)} history entry(ies) for {target_type}/{name}",
    )


def read_dispatch_log(ctx: ToolContext, last_n: int = 20) -> ToolResult:
    log = ctx.dispatch_log_ref[0] if ctx.dispatch_log_ref else []
    return _ok(log[-last_n:], f"{min(last_n, len(log))} of {len(log)} dispatches")


def patch_testplan(
    ctx: ToolContext,
    target_type: TargetType,
    name: str,
    fields: dict,
) -> ToolResult:
    plan = _plan(ctx)
    if plan is None:
        return _err("patch_testplan: no plan", "ToolContext.testplan_ref empty")
    item = _find(plan, target_type, name)
    if item is None:
        return _err("patch_testplan: not found", f"no {target_type} named {name!r}")

    if "history" in fields:
        return _err(
            "patch_testplan: history is append-only",
            "use append_history(); patch_testplan cannot modify the history array",
        )
    if "name" in fields:
        return _err("patch_testplan: name is immutable", "cannot rename items")

    try:
        updated = item.model_copy(update=fields)
        # Re-validate via Pydantic round-trip
        cls = type(item)
        cls.model_validate(updated.model_dump())
    except Exception as exc:  # pydantic ValidationError or others
        return _err("patch_testplan: validation failed", str(exc))

    items = _items(plan, target_type)
    idx = items.index(item)
    items[idx] = updated

    if ctx.emit is not None:
        by = "orchestrate" if ctx.node == "orchestrate" else (ctx.node or "unknown")
        ctx.emit(
            "testplan.patched",
            {
                "target_type": target_type,
                "name": name,
                "fields_changed": list(fields.keys()),
                "by": by,
            },
            iteration=ctx.iteration,
            node=ctx.node,
            agent_id=ctx.agent_id,
            dispatch_id=ctx.dispatch_id,
        )
    return _ok(
        updated.model_dump(),
        f"patched {target_type}/{name}: {list(fields.keys())}",
    )


def append_history(
    ctx: ToolContext,
    target_type: TargetType,
    name: str,
    outcome: str,
    summary: str,
    artifacts_path: str | None = None,
    agent_id: str | None = None,
) -> ToolResult:
    plan = _plan(ctx)
    if plan is None:
        return _err("append_history: no plan", "ToolContext.testplan_ref empty")
    item = _find(plan, target_type, name)
    if item is None:
        return _err("append_history: not found", f"no {target_type} named {name!r}")
    try:
        entry = HistoryEntry(
            timestamp=iso_now(),
            agent_id=agent_id or (ctx.agent_id or "orchestrator"),
            outcome=outcome,  # type: ignore[arg-type]
            summary=summary,
            artifacts_path=artifacts_path,
        )
    except Exception as exc:
        return _err("append_history: validation failed", str(exc))
    item.history.append(entry)
    if ctx.emit is not None:
        ctx.emit(
            "testplan.history_appended",
            {
                "target_type": target_type,
                "name": name,
                "outcome": outcome,
                "agent_id": entry.agent_id,
            },
            iteration=ctx.iteration,
            node=ctx.node,
            agent_id=ctx.agent_id,
            dispatch_id=ctx.dispatch_id,
        )
    return _ok(entry.model_dump(), f"history += {outcome} on {target_type}/{name}")


def build_testplan(ctx: ToolContext, plan: dict) -> ToolResult:
    """INIT-only — install a freshly-constructed testplan into state.

    `mode` is always overridden from `ctx.coverage_mode` — the run config
    already locks it, so any value the LLM passes is ignored to prevent
    accidental mode flips and to relieve the agent of having to remember it.
    """
    if not ctx.testplan_ref:
        return _err("build_testplan: no ref", "ToolContext.testplan_ref empty")
    plan = {**plan, "mode": ctx.coverage_mode}
    try:
        new_plan = Testplan.model_validate(plan)
    except Exception as exc:
        return _err("build_testplan: validation failed", str(exc))
    ctx.testplan_ref[0] = new_plan
    return _ok(
        {
            "mode": new_plan.mode,
            "testpoints": len(new_plan.testpoints),
            "covergroups": len(new_plan.covergroups),
            "code_scopes": len(new_plan.code_scopes),
        },
        f"installed testplan in mode={new_plan.mode}",
    )
