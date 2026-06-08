"""Questa adapter — ported from legacy_src/simulators/questasim_adapter.py.

Wraps `vlog`, `vsim`, and `vcover` from a Questa installation. Default
install path is `/opt/siemens/questasim/linux_x86_64`; override at
construction time if it lives elsewhere.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Literal

from covagent.simulators._questa_helpers import (
    DEFAULT_SIM_PATH,
    parse_text_functional_coverage,
    parse_xml_code_coverage,
    vcover_merge_command,
    vcover_text_report_command,
    vcover_xml_report_command,
    vlog_commands,
    vlog_commands_no_cover,
    vlog_succeeded,
    vsim_command,
)
from covagent.simulators.base import (
    CompileResult,
    CoverageSummary,
    MergeResult,
    RunResult,
    SimulatorAdapter,
)

_log = logging.getLogger(__name__)


class QuestaAdapter(SimulatorAdapter):
    name = "questa"

    def __init__(self, sim_path: Path | None = None) -> None:
        self.sim_path = Path(sim_path) if sim_path else DEFAULT_SIM_PATH
        if not (self.sim_path / "vlog").exists():
            _log.warning(
                "Questa binaries not found at %s. Set COVAGENT_QUESTA_PATH "
                "(or QUESTA_PATH) in .env to your install dir.",
                self.sim_path,
            )

    def extension(self) -> str:
        return ".ucdb"

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
        all_stdout: list[str] = []
        all_stderr: list[str] = []
        last_rc = 0

        try:
            # Pass 1: dependencies without coverage
            if compile_deps:
                for cmd in vlog_commands_no_cover(self.sim_path, list(compile_deps)):
                    res = subprocess.run(
                        cmd, cwd=str(work_dir), capture_output=True, text=True,
                        timeout=timeout_s,
                    )
                    all_stdout.append(res.stdout)
                    all_stderr.append(res.stderr)
                    last_rc = res.returncode
                    if not vlog_succeeded(res.stdout):
                        log_path = self._write_log(work_dir, "compile.log", all_stdout, all_stderr)
                        return CompileResult(
                            ok=False, error="dep compile failed",
                            duration_s=time.monotonic() - t0,
                            log_path=log_path, return_code=last_rc,
                            stdout="\n".join(all_stdout), stderr="\n".join(all_stderr),
                        )

            # Pass 2: design + testbench WITH coverage
            for cmd in vlog_commands(
                self.sim_path, list(sources),
                extra_incdirs=list(compile_deps or []),
                functional_coverage=False,
            ):
                res = subprocess.run(
                    cmd, cwd=str(work_dir), capture_output=True, text=True,
                    timeout=timeout_s,
                )
                all_stdout.append(res.stdout)
                all_stderr.append(res.stderr)
                last_rc = res.returncode
                if not vlog_succeeded(res.stdout):
                    log_path = self._write_log(work_dir, "compile.log", all_stdout, all_stderr)
                    return CompileResult(
                        ok=False, error="vlog reported errors",
                        duration_s=time.monotonic() - t0,
                        log_path=log_path, return_code=last_rc,
                        stdout="\n".join(all_stdout), stderr="\n".join(all_stderr),
                    )

            log_path = self._write_log(work_dir, "compile.log", all_stdout, all_stderr)
            return CompileResult(
                ok=True, duration_s=time.monotonic() - t0,
                log_path=log_path, return_code=last_rc,
                stdout="\n".join(all_stdout), stderr="\n".join(all_stderr),
            )
        except subprocess.TimeoutExpired:
            return CompileResult(
                ok=False, error=f"compile timeout after {timeout_s}s",
                duration_s=time.monotonic() - t0, return_code=124,
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
        if test_name is None:
            return RunResult(ok=False, error="test_name required for Questa run")
        work_dir.mkdir(parents=True, exist_ok=True)
        cov_dir = work_dir / "coverage"
        cov_dir.mkdir(parents=True, exist_ok=True)

        ucdb_files: list[Path] = []
        all_stdout: list[str] = []
        all_stderr: list[str] = []
        timed_out = 0

        for run_idx in range(num_runs):
            ucdb_path = cov_dir / f"run_{run_idx}.ucdb"
            cmd = vsim_command(self.sim_path, test_name, ucdb_path)
            try:
                res = subprocess.run(
                    cmd, cwd=str(work_dir), capture_output=True, text=True,
                    timeout=timeout_s,
                )
                stdout = res.stdout
                if not stdout.strip():
                    transcript = work_dir / "transcript"
                    if transcript.exists():
                        try:
                            stdout = transcript.read_text()
                        except OSError:
                            pass
                all_stdout.append(f"=== run {run_idx} ===\n{stdout}")
                all_stderr.append(res.stderr)
                if vlog_succeeded(stdout) and ucdb_path.exists():
                    # vlog_succeeded checks for "Errors: 0,"; vsim output may have it too.
                    ucdb_files.append(ucdb_path)
                elif ucdb_path.exists():
                    # Sim may not always print Errors: line; if UCDB written, accept.
                    ucdb_files.append(ucdb_path)
            except subprocess.TimeoutExpired:
                timed_out += 1
                all_stdout.append(f"=== run {run_idx} === TIMEOUT after {timeout_s}s")

        log_path = self._write_log(work_dir, "sim.log", all_stdout, all_stderr)

        if not ucdb_files:
            return RunResult(
                ok=False, error=f"no successful runs (timeouts: {timed_out}/{num_runs})",
                duration_s=time.monotonic() - t0, log_path=log_path,
                stdout="\n".join(all_stdout), stderr="\n".join(all_stderr),
            )

        # Merge into the requested coverage_db output (or first run's UCDB).
        target = coverage_db or (cov_dir / "merged.ucdb")
        target.parent.mkdir(parents=True, exist_ok=True)
        if len(ucdb_files) == 1:
            shutil.copy2(ucdb_files[0], target)
        else:
            cmd = vcover_merge_command(self.sim_path, target, ucdb_files)
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                return RunResult(
                    ok=False, error=f"merge failed: {res.stderr[:500]}",
                    duration_s=time.monotonic() - t0, log_path=log_path,
                )

        return RunResult(
            ok=True, duration_s=time.monotonic() - t0,
            coverage_db=target, log_path=log_path,
            runs_completed=len(ucdb_files),
            stdout="\n".join(all_stdout), stderr="\n".join(all_stderr),
        )

    def merge_coverage(
        self, master: Path, deltas: list[Path], output: Path
    ) -> MergeResult:
        t0 = time.monotonic()
        inputs = [p for p in [master] + list(deltas) if p.exists() and p.stat().st_size > 0]
        if not inputs:
            output.write_bytes(b"")
            return MergeResult(ok=True, output=output, duration_s=time.monotonic() - t0)
        if len(inputs) == 1:
            shutil.copy2(inputs[0], output)
            return MergeResult(ok=True, output=output, duration_s=time.monotonic() - t0)
        cmd = vcover_merge_command(self.sim_path, output, inputs)
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            return MergeResult(
                ok=False, error=res.stderr[:500],
                duration_s=time.monotonic() - t0,
            )
        return MergeResult(ok=True, output=output, duration_s=time.monotonic() - t0)

    def parse_coverage(
        self, db: Path, mode: Literal["functional", "code"]
    ) -> CoverageSummary:
        if not db.exists() or db.stat().st_size == 0:
            return CoverageSummary()
        if mode == "code":
            xml_out = db.parent / f"{db.stem}_report.xml"
            cmd = vcover_xml_report_command(self.sim_path, db, xml_out)
            subprocess.run(cmd, cwd=str(db.parent), capture_output=True, text=True)
            data = parse_xml_code_coverage(xml_out)
        else:
            txt_out = db.parent / f"{db.stem}_funcov.txt"
            cmd = vcover_text_report_command(self.sim_path, db, txt_out)
            subprocess.run(cmd, capture_output=True, text=True)
            data = parse_text_functional_coverage(txt_out)
        return CoverageSummary(
            overall_pct=data["overall_pct"],
            items_hit=data["items_hit"],
            items_total=data["items_total"],
            breakdown=data["breakdown"],
            unhit_items=data["unhit"][:200],
            raw={"db": str(db), "mode": mode},
        )

    @staticmethod
    def _write_log(
        work_dir: Path, name: str, stdout_chunks: list[str], stderr_chunks: list[str]
    ) -> Path:
        log_path = work_dir / name
        log_path.write_text(
            "=== STDOUT ===\n" + "\n".join(stdout_chunks)
            + "\n=== STDERR ===\n" + "\n".join(stderr_chunks)
        )
        return log_path
