"""Coverage snapshot helpers — copy master DB to per-iteration snapshot path."""

from __future__ import annotations

import shutil
from pathlib import Path


def take_snapshot(master: Path, snapshots_dir: Path, iteration: int) -> Path:
    """Copy master to <snapshots_dir>/iter_<NNN><ext> and return the path."""
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    target = snapshots_dir / f"iter_{iteration:03d}{master.suffix}"
    if master.exists():
        shutil.copy2(master, target)
    else:
        target.write_bytes(b"")
    return target
