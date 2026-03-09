import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple, Dict
import re
import logging

def build_vlog_command(simulator_path: Path, testbench: Path, design_files: List[Path]) -> List[str]:
    """Build vlog compilation command with coverage enabled."""
    return [
        str(simulator_path / "vlog"),
        "-sv",  # SystemVerilog mode
        "+cover=s",  # Statement coverage
        str(testbench)
    ] + [str(f) for f in design_files]


def _collect_incdirs(files: List[Path]) -> List[str]:
    """Collect unique parent directories as +incdir+ flags for include resolution."""
    dirs = set()
    for f in files:
        dirs.add(str(Path(f).parent))
    return [f"+incdir+{d}" for d in sorted(dirs)]


def build_vlog_commands(simulator_path: Path, testbench: Path, design_files: List[Path],
                        incdir_files: List[Path] = None) -> List[List[str]]:
    """Build vlog compilation commands, splitting Verilog and SystemVerilog files.

    Legacy .v files may use identifiers (e.g. ``return``) that are reserved
    keywords in SystemVerilog.  Compiling them with ``-sv`` causes parse
    errors.  We therefore emit **two** commands:

    1. ``.v`` files compiled in Verilog mode (no ``-sv``).
    2. ``.sv`` files compiled in SystemVerilog mode (with ``-sv``).

    Both write into the same ``work`` library so all modules remain visible.

    Args:
        incdir_files: Additional files whose parent directories will be added
            as +incdir+ search paths for `include resolution.
    """
    all_files = [testbench] + list(design_files)
    incdir_sources = list(all_files) + list(incdir_files or [])
    incdirs = _collect_incdirs(incdir_sources)

    v_files = [f for f in all_files if str(f).endswith('.v')]
    sv_files = [f for f in all_files if not str(f).endswith('.v')]

    commands: List[List[str]] = []
    vlog = str(simulator_path / "vlog")

    if v_files:
        commands.append([vlog, "+cover=s"] + incdirs + [str(f) for f in v_files])
    if sv_files:
        commands.append([vlog, "-sv", "+cover=s"] + incdirs + [str(f) for f in sv_files])

    return commands

def build_vlog_commands_no_cover(simulator_path: Path, files: List[Path]) -> List[List[str]]:
    """Build vlog commands WITHOUT coverage for compile-only dependencies.

    Same .v/.sv splitting logic as build_vlog_commands, but omits +cover=s.
    Adds +incdir+ from all file parent directories for include resolution.
    """
    v_files = [f for f in files if str(f).endswith('.v')]
    sv_files = [f for f in files if not str(f).endswith('.v')]
    incdirs = _collect_incdirs(files)

    commands: List[List[str]] = []
    vlog = str(simulator_path / "vlog")

    if v_files:
        commands.append([vlog] + incdirs + [str(f) for f in v_files])
    if sv_files:
        commands.append([vlog, "-sv"] + incdirs + [str(f) for f in sv_files])

    return commands


def build_vsim_command(simulator_path: Path, ucdb_path: Path) -> List[str]:
    """Build vsim simulation command with coverage collection."""
    do_script = f"coverage exclude -du tb_llm;coverage save -onexit {ucdb_path};run -all;exit;"
    return [
        str(simulator_path / "vsim"),
        "work.tb_llm",  # Work library + module name
        "-coverage",
        "-sv_seed", "random",
        "-c",  # Command-line mode
        "-suppress", "vsim-3009",   # timescale mismatch (compile_deps compiled without timescale)
        "-suppress", "vsim-3999",   # enum-to-logic port type mismatch
        "-do", do_script
    ]

def build_vcover_merge_command(simulator_path: Path, output: Path, input_ucdbs: List[Path]) -> List[str]:
    """Build vcover merge command."""
    # Validate all inputs exist
    missing = [str(u) for u in input_ucdbs if not u.exists()]
    if missing:
        raise FileNotFoundError(f"Missing UCDB files: {missing}")

    return [
        str(simulator_path / "vcover"),
        "merge",
        "-recursive",
        "-out", str(output)
    ] + [str(u) for u in input_ucdbs]

def build_coverage_report_command(simulator_path: Path, ucdb: Path, xml_output: Path) -> List[str]:
    """Build command to generate XML coverage report."""
    do_script = f"coverage report -output {xml_output} -du=* -detail -annotate -code s -xml;exit;"
    return [
        str(simulator_path / "vsim"),
        "-viewcov", str(ucdb),
        "-c",
        "-do", do_script
    ]

def check_questasim_success(output: str) -> bool:
    """
    Check if QuestaSim command succeeded by parsing output.
    Based on legacy questasim.py pattern.
    """
    if not output:
        return False

    lines = output.splitlines()
    if not lines:
        return False

    # Parse last line: "# Errors: 0, Warnings: X"
    split_line = re.split(r'[#,:]', lines[-1])
    stripped = [item.strip() for item in split_line]
    cleaned = [x for x in stripped if x]

    logging.debug(f"QuestaSim output check: {cleaned}")

    if len(cleaned) < 4:
        return False

    # Check "Errors: 0"
    return cleaned[0] == "Errors" and cleaned[1] == "0"

def parse_coverage_xml(xml_path: Path) -> Tuple[float, Dict[str, float], Dict[str, List[int]]]:
    """
    Parse QuestaSim coverage XML report.

    Returns:
        (total_coverage, module_breakdown, uncovered_lines)
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        total_active = 0
        total_hits = 0
        module_breakdown = {}
        uncovered_lines = {}

        for du_data in root.findall('.//DuData'):
            du_name = du_data.get('du')

            # Skip testbench from coverage
            if du_name == 'tb_llm':
                continue

            # Get file path
            file_map = du_data.find('.//fileMap')
            file_path = file_map.get('path') if file_map is not None else "unknown"

            # Get coverage stats
            statements = du_data.find('statements')
            if statements is not None:
                active = int(statements.get('active', 0))
                hits = int(statements.get('hits', 0))
                percent = float(statements.get('percent', 0.0))

                total_active += active
                total_hits += hits
                module_breakdown[du_name] = percent

                # Extract uncovered lines
                uncovered = []
                for stmt in du_data.findall('.//stmt'):
                    if stmt.get('hits') == '0':
                        line_num = int(stmt.get('ln'))
                        uncovered.append(line_num)

                if uncovered:
                    uncovered_lines[file_path] = uncovered

        total_coverage = (total_hits / total_active * 100.0) if total_active > 0 else 0.0

        return total_coverage, module_breakdown, uncovered_lines

    except (ET.ParseError, FileNotFoundError) as e:
        logging.error(f"Coverage XML parsing failed: {e}")
        return 0.0, {}, {}
