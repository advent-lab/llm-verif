"""Per-agent sandbox enforcement for write paths."""

from __future__ import annotations

from pathlib import Path


class OutOfScopeError(Exception):
    def __init__(self, candidate: Path, sandbox_root: Path) -> None:
        super().__init__(
            f"Path {candidate} is outside the sandbox {sandbox_root}"
        )
        self.candidate = candidate
        self.sandbox_root = sandbox_root


def resolve_write_path(sandbox_root: Path, raw_path: str) -> Path:
    root = Path(sandbox_root).resolve()
    candidate = (root / raw_path).resolve()
    if not _is_relative_to(candidate, root):
        raise OutOfScopeError(candidate, root)
    return candidate


def resolve_read_path(allowed_roots: list[Path], raw_path: str) -> Path:
    raw = Path(raw_path)
    candidate = raw.resolve() if raw.is_absolute() else None
    for root_raw in allowed_roots:
        root = Path(root_raw).resolve()
        if candidate is not None:
            if _is_relative_to(candidate, root):
                return candidate
        else:
            joined = (root / raw_path).resolve()
            if _is_relative_to(joined, root):
                return joined
    raise OutOfScopeError(candidate or Path(raw_path), Path(allowed_roots[0]))


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False
