"""MockAdapter — used by tests and any dev scenario without a real simulator.

Behavior:
- compile() returns ok=True if all sources exist.
- run() touches an empty coverage_db file and returns ok=True.
- merge_coverage() concatenates input deltas into the output (text); ok=True.
- parse_coverage() returns a deterministic synthetic summary based on filename.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Literal

from covagent.simulators.base import (
    CompileResult,
    CoverageSummary,
    MergeResult,
    RunResult,
    SimulatorAdapter,
)


class MockAdapter(SimulatorAdapter):
    name = "mock"

    def extension(self) -> str:
        return ".mockcov"

    def compile(
        self,
        sources: list[Path],
        work_dir: Path,
        *,
        top: str | None = None,
        timeout_s: int = 300,
        compile_deps: list[Path] | None = None,
    ) -> CompileResult:
        t0 = time.monotonic()
        work_dir.mkdir(parents=True, exist_ok=True)
        missing = [str(s) for s in sources if not Path(s).exists()]
        if missing:
            return CompileResult(
                ok=False,
                error=f"missing sources: {missing}",
                duration_s=time.monotonic() - t0,
                return_code=1,
            )
        log = work_dir / "compile.log"
        log.write_text(f"mock compile of {len(sources)} sources, top={top}\n")
        return CompileResult(
            ok=True, duration_s=time.monotonic() - t0, log_path=log, return_code=0
        )

    def run(
        self,
        work_dir: Path,
        *,
        test_name: str | None = None,
        coverage_db: Path | None = None,
        num_runs: int = 1,
        timeout_s: int = 600,
    ) -> RunResult:
        t0 = time.monotonic()
        work_dir.mkdir(parents=True, exist_ok=True)
        cov = coverage_db or (work_dir / f"coverage{self.extension()}")
        cov.parent.mkdir(parents=True, exist_ok=True)
        cov.write_bytes(b"mock-cov\n" + (test_name or "test").encode() + b"\n")
        log = work_dir / "sim.log"
        log.write_text(f"mock run test={test_name} runs={num_runs}\n")
        return RunResult(
            ok=True,
            duration_s=time.monotonic() - t0,
            coverage_db=cov,
            log_path=log,
            runs_completed=num_runs,
        )

    def merge_coverage(
        self, master: Path, deltas: list[Path], output: Path
    ) -> MergeResult:
        t0 = time.monotonic()
        output.parent.mkdir(parents=True, exist_ok=True)
        body = b""
        if master.exists():
            body += master.read_bytes()
        for d in deltas:
            if d.exists():
                body += d.read_bytes()
        output.write_bytes(body)
        return MergeResult(
            ok=True, duration_s=time.monotonic() - t0, output=output
        )

    def parse_coverage(
        self, db: Path, mode: Literal["functional", "code"]
    ) -> CoverageSummary:
        if not db.exists():
            return CoverageSummary()
        # Deterministic synthetic percentage from file content hash.
        h = hashlib.sha1(db.read_bytes()).hexdigest()
        pct = (int(h[:4], 16) % 10000) / 100.0
        return CoverageSummary(
            overall_pct=pct,
            items_hit=int(pct),
            items_total=100,
            breakdown={"mock_scope": pct},
            raw={"db": str(db), "mode": mode},
        )
