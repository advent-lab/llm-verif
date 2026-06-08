"""Read-only context tools — read_rtl, read_spec_excerpt, read_sim_log."""

from __future__ import annotations

from pathlib import Path

from covagent.tools.types import ToolContext, ToolResult
from covagent.workspace.sandbox import OutOfScopeError, resolve_read_path, resolve_write_path


def _err(summary: str, error: str) -> ToolResult:
    return {"ok": False, "data": None, "error": error, "summary": summary}


def _ok(data: object, summary: str) -> ToolResult:
    return {"ok": True, "data": data, "error": None, "summary": summary}


def _read_lines(p: Path, line_start: int | None, line_end: int | None) -> tuple[str, int, int]:
    raw = p.read_text(errors="replace").splitlines()
    n = len(raw)
    s = max(1, line_start) if line_start else 1
    e = min(n, line_end) if line_end else n
    body = "\n".join(raw[s - 1 : e])
    return body, s, e


def read_rtl(
    ctx: ToolContext,
    path: str,
    line_start: int | None = None,
    line_end: int | None = None,
) -> ToolResult:
    if ctx.design_root is None:
        return _err("read_rtl: no design_root", "ToolContext.design_root not set")
    try:
        p = resolve_read_path([ctx.design_root], path)
    except OutOfScopeError as e:
        return _err("read_rtl: out of scope", str(e))
    if not p.exists():
        return _err("read_rtl: not found", f"{p} does not exist")
    body, s, e = _read_lines(p, line_start, line_end)
    if len(body) > ctx.max_read_bytes:
        body = body[: ctx.max_read_bytes] + "\n... [truncated]"
    return _ok(
        {"path": str(p), "content": body, "line_start": s, "line_end": e},
        f"read {p.name} lines {s}-{e}",
    )


def read_spec_excerpt(
    ctx: ToolContext,
    query: str,
    section: str | None = None,
    max_chars: int = 4000,
) -> ToolResult:
    """Naive spec retrieval: scan all spec files, return matching paragraphs.

    A real RAG layer can replace this without changing the tool surface.
    """
    if ctx.design_root is None:
        return _err("read_spec_excerpt: no design_root", "ToolContext.design_root not set")

    files: list[Path] = []
    for ext in ("*.md", "*.txt", "*.rst"):
        files.extend(Path(ctx.design_root).rglob(ext))

    needle = (section or query).lower()
    matches: list[dict] = []
    budget = max_chars
    for f in files:
        try:
            text = f.read_text(errors="replace")
        except OSError:
            continue
        for para in text.split("\n\n"):
            if needle in para.lower():
                excerpt = para.strip()[: min(budget, 1200)]
                matches.append({"file": str(f), "excerpt": excerpt})
                budget -= len(excerpt)
                if budget <= 0:
                    break
        if budget <= 0:
            break

    if not matches:
        return _ok(
            {"matches": [], "query": query, "section": section},
            f"no spec excerpts matched '{query}'",
        )
    return _ok(
        {"matches": matches, "query": query, "section": section},
        f"found {len(matches)} spec excerpt(s) for '{query}'",
    )


def read_sim_log(ctx: ToolContext, path: str, tail_lines: int = 200) -> ToolResult:
    if ctx.work_dir is None:
        return _err("read_sim_log: no work_dir", "ToolContext.work_dir not set")
    try:
        p = resolve_write_path(ctx.work_dir, path)
    except OutOfScopeError as e:
        return _err("read_sim_log: out of scope", str(e))
    if not p.exists():
        return _err("read_sim_log: not found", f"{p} does not exist")
    raw = p.read_text(errors="replace").splitlines()
    body = "\n".join(raw[-tail_lines:])
    return _ok(
        {"path": str(p.relative_to(ctx.work_dir)), "tail": body, "total_lines": len(raw)},
        f"sim log tail ({len(raw)} total lines, last {min(tail_lines, len(raw))})",
    )
