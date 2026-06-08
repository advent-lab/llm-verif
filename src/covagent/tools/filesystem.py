"""Filesystem tools — read_file, write_file, edit_file. Sandbox-enforced writes."""

from __future__ import annotations

from pathlib import Path

from covagent.tools.types import ToolContext, ToolResult
from covagent.workspace.sandbox import OutOfScopeError, resolve_write_path


def _err(summary: str, error: str) -> ToolResult:
    return {"ok": False, "data": None, "error": error, "summary": summary}


def _ok(data: object, summary: str) -> ToolResult:
    return {"ok": True, "data": data, "error": None, "summary": summary}


def read_file(ctx: ToolContext, path: str, max_bytes: int | None = None) -> ToolResult:
    if ctx.work_dir is None:
        return _err("read_file: no work_dir", "ToolContext.work_dir not set")
    try:
        p = resolve_write_path(ctx.work_dir, path)
    except OutOfScopeError as e:
        return _err("read_file: out of scope", str(e))
    if not p.exists():
        return _err("read_file: not found", f"{p} does not exist")
    limit = max_bytes if max_bytes is not None else ctx.max_read_bytes
    raw = p.read_bytes()
    truncated = len(raw) > limit
    body = raw[:limit].decode(errors="replace")
    return _ok(
        {"path": str(p.relative_to(ctx.work_dir)), "content": body, "truncated": truncated, "bytes": len(raw)},
        f"read {len(raw)} bytes from {path}{' (truncated)' if truncated else ''}",
    )


def write_file(ctx: ToolContext, path: str, content: str) -> ToolResult:
    if ctx.work_dir is None:
        return _err("write_file: no work_dir", "ToolContext.work_dir not set")
    try:
        p = resolve_write_path(ctx.work_dir, path)
    except OutOfScopeError as e:
        return _err("write_file: out of scope", str(e))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return _ok(
        {"path": str(p.relative_to(ctx.work_dir)), "bytes": len(content)},
        f"wrote {len(content)} bytes to {path}",
    )


def edit_file(
    ctx: ToolContext,
    path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> ToolResult:
    if ctx.work_dir is None:
        return _err("edit_file: no work_dir", "ToolContext.work_dir not set")
    try:
        p = resolve_write_path(ctx.work_dir, path)
    except OutOfScopeError as e:
        return _err("edit_file: out of scope", str(e))
    if not p.exists():
        return _err("edit_file: not found", f"{p} does not exist")
    text = p.read_text()
    count = text.count(old_string)
    if count == 0:
        return _err("edit_file: no match", f"old_string not found in {path}")
    if count > 1 and not replace_all:
        return _err(
            "edit_file: ambiguous",
            f"old_string matches {count} times in {path}; pass replace_all=true or anchor more context",
        )
    new_text = text.replace(old_string, new_string) if replace_all else text.replace(old_string, new_string, 1)
    p.write_text(new_text)
    return _ok(
        {
            "path": str(p.relative_to(ctx.work_dir)),
            "replacements": count if replace_all else 1,
            "bytes_after": len(new_text),
        },
        f"edited {path} ({count if replace_all else 1} replacement{'s' if (count if replace_all else 1) != 1 else ''})",
    )
