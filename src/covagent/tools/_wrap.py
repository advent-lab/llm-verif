"""Tool wrapping — adds event emission around every LLM-facing tool call."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from covagent.tools.types import ToolContext, ToolResult


def _summary_from_args(args: dict) -> dict:
    """Trim arg dict for event payload — drop bulky `content` / `new_string` blobs."""
    out = {}
    for k, v in args.items():
        if isinstance(v, str) and len(v) > 200:
            out[k] = f"<{len(v)} chars>"
        else:
            out[k] = v
    return out


def call_with_events(
    ctx: ToolContext,
    tool_name: str,
    fn: Callable[..., ToolResult],
    args: dict,
) -> ToolResult:
    """Invoke a tool function, emitting tool.called / tool.returned events."""
    if ctx.emit is not None:
        ctx.emit(
            "tool.called",
            {
                "tool_name": tool_name,
                "args": _summary_from_args(args),
                "conversation": (
                    f"agent:{ctx.agent_id}"
                    if ctx.conversation == "agent"
                    else ctx.conversation
                ),
            },
            iteration=ctx.iteration,
            node=ctx.node,
            agent_id=ctx.agent_id,
            dispatch_id=ctx.dispatch_id,
        )

    t0 = time.monotonic()
    result: ToolResult
    try:
        result = fn(**args)
    except Exception as exc:
        result = {
            "ok": False,
            "data": None,
            "error": f"{type(exc).__name__}: {exc}",
            "summary": f"{tool_name} raised {type(exc).__name__}",
        }
    duration_s = time.monotonic() - t0

    if ctx.emit is not None:
        ctx.emit(
            "tool.returned",
            {
                "tool_name": tool_name,
                "ok": result.get("ok", False),
                "summary": result.get("summary", ""),
                "error": result.get("error"),
                "duration_s": round(duration_s, 4),
            },
            iteration=ctx.iteration,
            node=ctx.node,
            agent_id=ctx.agent_id,
            dispatch_id=ctx.dispatch_id,
        )
    return result


def make_callable(ctx: ToolContext, tool_name: str, fn: Callable[..., ToolResult]):
    """Return a thin callable that injects ctx and emits events.

    The returned callable's signature is the same as `fn` minus the `ctx`
    keyword — args go through unchanged. Used by tool factories to produce
    LangChain `StructuredTool` callables.
    """

    def _wrapped(**kwargs: Any) -> ToolResult:
        return call_with_events(ctx, tool_name, fn, kwargs)

    _wrapped.__name__ = tool_name
    return _wrapped
