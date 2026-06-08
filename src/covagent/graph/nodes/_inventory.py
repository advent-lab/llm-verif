"""Shared file-inventory helper for prompt rendering.

Init and orchestrate both need to show the LLM a categorized list of files
under `design_root`, with paths relative to that root so they can be passed
straight to `read_rtl` / `read_spec_excerpt`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from covagent.workspace.dashboard import DesignEntry


class FileInventory(TypedDict):
    design_root: str
    design_files: list[str]
    design_context_files: list[str]
    spec_files: list[str]


def file_inventory(entry: DesignEntry | None) -> FileInventory:
    """Return categorized files relative to `entry.design_root`.

    Empty lists / empty design_root if `entry` is None (test/replay flows
    that don't carry a real design entry).
    """
    if entry is None:
        return FileInventory(
            design_root="", design_files=[], design_context_files=[], spec_files=[]
        )

    root = entry.design_root

    def _rel(paths: list[Path]) -> list[str]:
        out: list[str] = []
        for p in paths:
            try:
                out.append(str(Path(p).relative_to(root)))
            except ValueError:
                out.append(str(p))
        return out

    return FileInventory(
        design_root=str(root),
        design_files=_rel(entry.design),
        design_context_files=_rel(entry.design_context),
        spec_files=_rel(entry.spec),
    )
