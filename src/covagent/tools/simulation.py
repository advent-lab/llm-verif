"""run_sim tool — invokes simulator compile + run, returns structured result."""

from __future__ import annotations

from pathlib import Path

from covagent.tools.types import ToolContext, ToolResult


def _err(summary: str, error: str) -> ToolResult:
    return {"ok": False, "data": None, "error": error, "summary": summary}


def _ok(data: object, summary: str) -> ToolResult:
    return {"ok": True, "data": data, "error": None, "summary": summary}


def run_sim(
    ctx: ToolContext,
    testbench_name: str,
    sources: list[str] | None = None,
    timeout_s: int = 600,
    num_runs: int = 1,
) -> ToolResult:
    """Compile then simulate. Returns paths to log + per-dispatch coverage delta."""
    if ctx.simulator is None:
        return _err("run_sim: no simulator", "ToolContext.simulator not set")
    if ctx.work_dir is None:
        return _err("run_sim: no work_dir", "ToolContext.work_dir not set")

    src_paths: list[Path] = []
    work = Path(ctx.work_dir)
    if sources:
        for s in sources:
            p = (work / s) if not Path(s).is_absolute() else Path(s)
            src_paths.append(p)
    else:
        # Default: every .sv / .v under work_dir/tests/
        tests_dir = work / "tests"
        if tests_dir.exists():
            src_paths.extend(sorted(tests_dir.rglob("*.sv")))
            src_paths.extend(sorted(tests_dir.rglob("*.v")))

    # Prepend design files from the dashboard entry (DUT + context RTL).  These
    # must be in the instrumented sources list (not compile_deps) so Questa
    # measures their line/branch/toggle coverage.  Deduplicate by resolved path
    # to handle the case where an agent accidentally names a DUT file too.
    if ctx.design_files:
        agent_resolved = {p.resolve() for p in src_paths}
        design_prefix = [
            Path(f) for f in ctx.design_files
            if Path(f).resolve() not in agent_resolved
        ]
        src_paths = design_prefix + src_paths

    if not src_paths:
        return _err("run_sim: no sources", "no source files to compile")

    sim = ctx.simulator
    sim_dir = work / "sim"
    sim_dir.mkdir(parents=True, exist_ok=True)
    delta_path = work / "coverage" / f"delta{sim.extension()}"
    delta_path.parent.mkdir(parents=True, exist_ok=True)

    cr = sim.compile(src_paths, sim_dir, top=testbench_name, timeout_s=timeout_s)
    if not cr.ok:
        return _err(f"compile failed (rc={cr.return_code})", cr.error or "compile error")

    rr = sim.run(
        sim_dir,
        test_name=testbench_name,
        coverage_db=delta_path,
        num_runs=num_runs,
        timeout_s=timeout_s,
    )
    data = {
        "testbench": testbench_name,
        "sources": [str(s) for s in src_paths],
        "compile_log": str(cr.log_path) if cr.log_path else None,
        "sim_log": str(rr.log_path) if rr.log_path else None,
        "coverage_delta": str(rr.coverage_db) if rr.coverage_db else None,
        "compile_duration_s": cr.duration_s,
        "sim_duration_s": rr.duration_s,
        "ok": rr.ok,
        "error": rr.error,
        "runs_completed": rr.runs_completed,
    }
    summary = (
        f"sim {testbench_name}: compile {cr.duration_s:.1f}s, "
        f"run {rr.duration_s:.1f}s, {'OK' if rr.ok else 'FAIL'}"
    )
    return _ok(data, summary)
