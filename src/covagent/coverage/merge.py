"""Internal coverage merge — called only from update_state. Not LLM-callable."""

from __future__ import annotations

import shutil
from pathlib import Path

from covagent.simulators.base import MergeResult, SimulatorAdapter


def merge_deltas(
    sim: SimulatorAdapter,
    master: Path,
    deltas: list[Path],
    *,
    baseline: Path | None = None,
) -> MergeResult:
    """Merge per-dispatch coverage deltas into master.

    Atomicity: write to a temp output, then move into place. If master
    doesn't exist yet, seed from baseline (if provided) or start empty.
    Per coverage.md: failures are loud — caller (update_state) decides
    whether to mark dispatches as merge_failed and continue.
    """
    master.parent.mkdir(parents=True, exist_ok=True)
    if not master.exists():
        if baseline is not None and baseline.exists():
            shutil.copy2(baseline, master)
        else:
            master.write_bytes(b"")

    if not deltas:
        return MergeResult(ok=True, output=master)

    tmp = master.with_suffix(master.suffix + ".tmp")
    result = sim.merge_coverage(master, deltas, tmp)
    if not result.ok:
        # Ensure tmp doesn't pollute the master path on failure.
        if tmp.exists():
            tmp.unlink()
        return result
    tmp.replace(master)
    return MergeResult(
        ok=True, output=master, duration_s=result.duration_s
    )
