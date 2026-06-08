"""Questa command-line builders + parsers.

Distilled from legacy_src/utils/questasim.py — keeps the working command
forms but drops the legacy-specific top-module name (`tb_llm`) hard-coding;
the new framework passes `top` explicitly.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

# Convenience default for the standard Siemens Questa install layout.
# Other developers will almost certainly need to override this via
# `COVAGENT_QUESTA_PATH` / `QUESTA_PATH` in `.env` (or the `sim_path` kwarg
# when constructing `QuestaAdapter` directly).
DEFAULT_SIM_PATH = Path("/opt/siemens/questasim/linux_x86_64")


def _incdirs(files: list[Path]) -> list[str]:
    dirs = sorted({str(Path(f).parent) for f in files})
    return [f"+incdir+{d}" for d in dirs]


def vlog_commands(
    sim_path: Path,
    sources: list[Path],
    *,
    functional_coverage: bool = False,
    extra_incdirs: list[Path] | None = None,
) -> list[list[str]]:
    """Compile commands. Splits .v and .sv to avoid SV-keyword collisions."""
    files = list(sources)
    incdirs_files = files + list(extra_incdirs or [])
    incdirs = _incdirs(incdirs_files)
    cover_flag = "+cover=sbfec" if functional_coverage else "+cover=s"
    vlog = str(sim_path / "vlog")

    v_files = [f for f in files if str(f).endswith(".v")]
    sv_files = [f for f in files if not str(f).endswith(".v")]

    commands: list[list[str]] = []
    if v_files:
        commands.append([vlog, cover_flag] + incdirs + [str(f) for f in v_files])
    if sv_files:
        commands.append(
            [vlog, "-sv", cover_flag] + incdirs + [str(f) for f in sv_files]
        )
    return commands


def vlog_commands_no_cover(sim_path: Path, sources: list[Path]) -> list[list[str]]:
    """Compile dependencies WITHOUT coverage instrumentation."""
    files = list(sources)
    incdirs = _incdirs(files)
    vlog = str(sim_path / "vlog")
    v_files = [f for f in files if str(f).endswith(".v")]
    sv_files = [f for f in files if not str(f).endswith(".v")]
    commands: list[list[str]] = []
    if v_files:
        commands.append([vlog] + incdirs + [str(f) for f in v_files])
    if sv_files:
        commands.append([vlog, "-sv"] + incdirs + [str(f) for f in sv_files])
    return commands


def vsim_command(sim_path: Path, top: str, ucdb_out: Path) -> list[str]:
    """Run command. `top` is the testbench module name (e.g. 'tb_lfsr')."""
    do_script = (
        f"coverage exclude -du {top};"
        f"coverage save -onexit {ucdb_out};"
        f"run -all;exit;"
    )
    return [
        str(sim_path / "vsim"),
        f"work.{top}",
        "-coverage",
        "-sv_seed", "random",
        "-c",
        "-suppress", "vsim-3009",
        "-suppress", "vsim-3999",
        "-do", do_script,
    ]


def vcover_merge_command(
    sim_path: Path, output: Path, inputs: list[Path]
) -> list[str]:
    return [
        str(sim_path / "vcover"),
        "merge",
        "-recursive",
        "-out", str(output),
    ] + [str(p) for p in inputs]


def vcover_xml_report_command(sim_path: Path, ucdb: Path, xml_out: Path) -> list[str]:
    """vsim-driven XML coverage report (line/statement)."""
    do_script = (
        f"coverage report -output {xml_out} -du=* -detail -annotate -code s -xml;exit;"
    )
    return [
        str(sim_path / "vsim"),
        "-viewcov", str(ucdb),
        "-c",
        "-do", do_script,
    ]


def vcover_text_report_command(sim_path: Path, ucdb: Path, text_out: Path) -> list[str]:
    """vcover text report — used for functional (covergroup) parsing."""
    return [
        str(sim_path / "vcover"),
        "report",
        "-details",
        "-output", str(text_out),
        str(ucdb),
    ]


_QUESTASIM_ERROR_RE = re.compile(r"^Errors:\s+(\d+),", re.MULTILINE)


def vlog_succeeded(stdout: str) -> bool:
    """Last 'Errors: N,' line indicates clean compile when N=0."""
    matches = _QUESTASIM_ERROR_RE.findall(stdout or "")
    if not matches:
        return False
    return matches[-1] == "0"


def parse_xml_code_coverage(xml_path: Path, exclude_top: str | None = None) -> dict:
    """Parse Questa XML report → overall pct + per-file breakdown + unhit lines."""
    if not xml_path.exists():
        return {"overall_pct": 0.0, "items_hit": 0, "items_total": 0, "breakdown": {}, "unhit": []}
    tree = ET.parse(xml_path)
    root = tree.getroot()

    total_active = 0
    total_hits = 0
    breakdown: dict[str, float] = {}
    unhit: list[str] = []

    for du_data in root.findall(".//DuData"):
        du_name = du_data.get("du")
        if exclude_top and du_name == exclude_top:
            continue
        file_map = du_data.find(".//fileMap")
        file_path = file_map.get("path") if file_map is not None else "unknown"

        statements = du_data.find("statements")
        if statements is None:
            continue
        active = int(statements.get("active", 0))
        hits = int(statements.get("hits", 0))
        pct = float(statements.get("percent", 0.0))
        total_active += active
        total_hits += hits
        breakdown[file_path] = pct

        for stmt in du_data.findall(".//stmt"):
            if stmt.get("hits") == "0":
                ln = stmt.get("ln")
                if ln:
                    unhit.append(f"{file_path}:{ln}")

    overall = (total_hits / total_active * 100.0) if total_active > 0 else 0.0
    return {
        "overall_pct": round(overall, 2),
        "items_hit": total_hits,
        "items_total": total_active,
        "breakdown": breakdown,
        "unhit": unhit,
    }


_TOTAL_FCOV_RE = re.compile(r"TOTAL COVERGROUP COVERAGE:\s+([\d.]+)%")
_INSTANCE_RE = re.compile(r"^ Covergroup instance\s+\\?/?(\w[\w/\\]*)\s+([\d.]+)%")


def parse_text_functional_coverage(text_path: Path) -> dict:
    """Parse vcover text report → overall pct + per-covergroup breakdown."""
    if not text_path.exists():
        return {"overall_pct": 0.0, "items_hit": 0, "items_total": 0, "breakdown": {}, "unhit": []}
    text = text_path.read_text(errors="replace")
    overall = 0.0
    m = _TOTAL_FCOV_RE.search(text)
    if m:
        overall = float(m.group(1))

    breakdown: dict[str, float] = {}
    for line in text.splitlines():
        im = _INSTANCE_RE.match(line)
        if im:
            raw = im.group(1).replace("\\", "").strip("/")
            cg_name = raw.split("/")[-1]
            breakdown[cg_name] = float(im.group(2))

    items_total = len(breakdown) or 1
    items_hit = sum(1 for pct in breakdown.values() if pct >= 100.0)
    return {
        "overall_pct": overall,
        "items_hit": items_hit,
        "items_total": items_total,
        "breakdown": breakdown,
        "unhit": [name for name, pct in breakdown.items() if pct < 100.0],
    }
