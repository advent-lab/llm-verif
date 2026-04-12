import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import re
import logging
import os


# ══════════════════════════════════════════════════════════════════════════════
# Command builders
# ══════════════════════════════════════════════════════════════════════════════

def build_vlog_command(simulator_path: Path, testbench: Path, design_files: List[Path]) -> List[str]:
    """Build vlog compilation command with coverage enabled."""
    # Check if functional coverage is enabled from environment
    funcov_enabled = os.getenv("FUNCTIONAL_COVERAGE_ENABLED", "0") == "1"

    cmd = [
        str(simulator_path / "vlog"),
        "-sv",  # SystemVerilog mode
    ]

    # Add coverage flags
    if funcov_enabled:
        cmd.extend(["-coveropt", "3", "+cover=sbfec"])  # Full coverage including functional
    else:
        cmd.append("+cover=s")  # Statement coverage only

    cmd.append(str(testbench))
    cmd.extend([str(f) for f in design_files])

    return cmd



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
    all_files = list(design_files) + [testbench]
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


# ══════════════════════════════════════════════════════════════════════════════
# Output checking and parsing helpers
# ══════════════════════════════════════════════════════════════════════════════

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
                    uncovered_lines[file_path] = sorted(uncovered)

        total_coverage = (total_hits / total_active * 100.0) if total_active > 0 else 0.0

        return total_coverage, module_breakdown, uncovered_lines

    except (ET.ParseError, FileNotFoundError) as e:
        logging.error(f"Coverage XML parsing failed: {e}")
        return 0.0, {}, {}

## ── UVM Command Builders ─────────────────────────────────────────────────────
#
# UVM compilation strategy (combined approach):
#
#   1. vlib work          – standard work library
#   2. vlib uvm_lib       – dedicated UVM library
#   3. vlog -sv -work uvm_lib  uvm_pkg.sv
#                         – compile UVM 1.2 from source with CURRENT QuestaSim
#                           (avoids vsim-12460 stale-binary errors from the
#                            pre-compiled /opt/siemens/questasim/uvm-1.2)
#   4. vmap mtiUvm uvm_lib
#                         – redirect QuestaSim's default mtiUvm (points to 1.1d
#                           in modelsim.ini) so the LibrarySearchPath loads our
#                           freshly compiled 1.2 instead of 1.1d
#   5. vlog -sv -mfcu -L uvm_lib -f filelist.f
#   6. vopt +acc <Top> -L uvm_lib -o opt_top +cover=bcestf
#
# This avoids TWO failure modes:
#   A. Dual-UVM conflict (mtiUvm 1.1d + uvm_lib 1.2) → INVTST factory errors
#   B. Stale pre-compiled UVM library → vsim-12460 / vsim-8754 type errors


def build_uvm_vlib_uvm_command(simulator_path: Path) -> List[str]:
    """Build vlib command to create a dedicated UVM library."""
    return [str(simulator_path / "vlib"), "uvm_lib"]


def build_uvm_vlog_uvm_command(simulator_path: Path, uvm_home: str) -> List[str]:
    """Compile UVM 1.2 from source into ``uvm_lib``.

    Must be compiled from source (not using the pre-compiled library at
    ``/opt/siemens/questasim/uvm-1.2``) because QuestaSim 2025.x added
    stricter type checks (vsim-12460, vsim-8754) that reject classes
    compiled with older QuestaSim versions.
    """
    return [
        str(simulator_path / "vlog"),
        "-sv",
        "-work", "uvm_lib",
        "+incdir+" + uvm_home + "/src",
        uvm_home + "/src/uvm_pkg.sv",
    ]


def build_uvm_vmap_command(simulator_path: Path) -> List[str]:
    """Redirect ``mtiUvm`` to our freshly compiled ``uvm_lib``.

    QuestaSim's ``modelsim.ini`` maps ``mtiUvm → uvm-1.1d`` and the
    ``LibrarySearchPath`` auto-loads ``mtiUvm`` during elaboration.
    Without this vmap, both UVM 1.1d *and* our UVM 1.2 are loaded,
    causing factory registration to silently fail (INVTST).
    """
    return [
        str(simulator_path / "vmap"),
        "mtiUvm",
        "uvm_lib",
    ]


def build_uvm_vlog_design_command(simulator_path: Path, filelist: Path, uvm_home: str) -> List[str]:
    """Compile design + testbench files with ``-mfcu -L uvm_lib``."""
    return [
        str(simulator_path / "vlog"),
        "-sv",
        "-mfcu",
        "+incdir+" + uvm_home + "/src",
        "-L", "uvm_lib",
        "-f", str(filelist),
    ]


def build_uvm_vopt_command(simulator_path: Path, top_module: str) -> List[str]:
    """Build vopt optimization command with full coverage instrumentation."""
    return [
        str(simulator_path / "vopt"),
        "+acc",
        top_module,
        "-L", "uvm_lib",
        "-o", "opt_top",
        "+cover=bcestf",
    ]


def build_uvm_vsim_command(
    simulator_path: Path,
    ucdb_path: Path,
    test_name: str,
    dpi_lib: str,
    seed: str = "random",
) -> List[str]:
    """Build vsim simulation command for UVM with coverage collection."""
    do_script = (
        f"coverage save -onexit {ucdb_path}; "
        f"run -all; quit"
    )
    return [
        str(simulator_path / "vsim"),
        "-c",
        "opt_top",
        "-coverage",
        "-sv_seed", seed,
        "-sv_lib", dpi_lib,
        f"+UVM_TESTNAME={test_name}",
        "+UVM_VERBOSITY=UVM_HIGH",
        "-do", do_script,
    ]


def parse_functional_coverage_text(report_path: Path) -> Dict:
    """
    Parse QuestaSim functional coverage text report.

    Args:
        report_path: Path to text coverage report (from vcover report -details -output)

    Returns:
        {
            'total_coverage': 60.02,
            'covergroups': [
                {
                    'name': 'cg_alu_inst',
                    'coverage': 30.46,
                    'uncovered_bins': ['invalid[8]', 'invalid[13]', ...]
                }
            ]
        }
    """
    if not report_path.exists():
        logging.error(f"Functional coverage report not found: {report_path}")
        return {'total_coverage': 0.0, 'covergroups': []}

    try:
        with open(report_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Extract total coverage
        total_coverage = 0.0
        match = re.search(r'TOTAL COVERGROUP COVERAGE:\s+([\d.]+)%', content)
        if match:
            total_coverage = float(match.group(1))

        # Extract covergroups
        covergroups = []
        cg_pattern = r'Covergroup instance\s+(\\?/?[\w/]+)\s+([\d.]+)%'
        for match in re.finditer(cg_pattern, content):
            cg_path = match.group(1).replace('\\/', '/')
            cg_name = cg_path.split('/')[-1]
            coverage = float(match.group(2))

            # Find uncovered bins in this covergroup's section
            # Look for lines like: "bin invalid[8]    0    1    -    ZERO"
            start_pos = match.start()
            next_cg = re.search(r'\n Covergroup instance', content[start_pos + 100:])
            section_end = start_pos + 100 + next_cg.start() if next_cg else len(content)
            section = content[start_pos:section_end]

            uncovered_bins = []
            bin_pattern = r'bin\s+([\w\[\]<>,\*\-]+)\s+0\s+1\s+-\s+ZERO'
            for bin_match in re.finditer(bin_pattern, section):
                uncovered_bins.append(bin_match.group(1))

            covergroups.append({
                'name': cg_name,
                'instance_path': cg_path,
                'coverage': coverage,
                'uncovered_bins': uncovered_bins
            })

        return {
            'total_coverage': total_coverage,
            'covergroups': covergroups
        }

    except Exception as e:
        logging.error(f"Functional coverage parsing failed: {e}")
        return {'total_coverage': 0.0, 'covergroups': [], 'error': str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# Coverage hole report generation
# ══════════════════════════════════════════════════════════════════════════════

def parse_functional_coverage_holes(report_path: Path) -> list:
    """
    Parse a QuestaSim functional coverage text report and extract all uncovered
    bins with their full covergroup → coverpoint → bin hierarchy.

    Only parses 'Covergroup instance' sections (not 'TYPE' sections) to avoid
    duplicating data that appears in both parts of the QuestaSim report.

    The parser is a line-by-line state machine:
      - OUTSIDE  : scanning for a 'Covergroup instance' header
      - IN_CG    : inside an instance block, scanning for coverpoint headers
      - IN_CP    : inside a coverpoint/cross block, scanning for ZERO bin lines

    'ignore_bin' entries are intentionally excluded from the output since they
    represent bins that the designer has explicitly waived.

    Args:
        report_path: Path to the cumulative functional coverage text report
                     (typically ``coverage/cumulative_functional_coverage.txt``).

    Returns:
        List of covergroup dicts, one per instance that has at least one
        uncovered bin::

            [
                {
                    'covergroup':            'cg_status_inst',
                    'instance_path':         '/tb_llm/cg_status_inst',
                    'coverage_pct':          95.0,
                    'uncovered_coverpoints': [
                        {
                            'name':           'cross_ready_valid',
                            'kind':           'Cross',
                            'coverage_pct':   75.0,
                            'uncovered_bins': ['busy_digest_hold'],
                        }
                    ],
                }
            ]

        Returns ``[]`` if the file cannot be read or contains no uncovered bins.
    """
    if not report_path.exists():
        logging.error(f"parse_functional_coverage_holes: report not found: {report_path}")
        return []

    try:
        with open(report_path, 'r', encoding='utf-8', errors='ignore') as fh:
            lines = fh.readlines()

        # ── Compiled patterns ─────────────────────────────────────────────
        # " Covergroup instance \/tb_llm/cg_name   95.00%  ..."
        instance_pat = re.compile(
            r'^ Covergroup instance\s+\\?/?([\w/\\]+)\s+([\d.]+)%'
        )
        # "    Coverpoint cp_name   75.00%  ..."  or  "    Cross cross_name   75.00%  ..."
        # Four leading spaces distinguish coverpoint lines from summary/stats lines.
        coverpoint_pat = re.compile(
            r'^    (Coverpoint|Cross)\s+(\w+)\s+([\d.]+)%'
        )
        # A ZERO (unhit) bin at any indentation level, e.g.:
        #   "        bin busy_digest_hold    0    1    -    ZERO"
        #   "            bin done_any_round  0    1    -    ZERO"
        # The leading-space anchor prevents matching 'ignore_bin' lines because
        # those start with the word "ignore_bin", not "bin".
        zero_bin_pat = re.compile(
            r'^\s+bin\s+([\w\[\]<>,\*\-\.]+)\s+0\s+1\s+-\s+ZERO'
        )
        # " TYPE /path ..." lines open the type-definition section; skip them.
        type_section_pat = re.compile(r'^ TYPE ')

        # ── State machine ─────────────────────────────────────────────────
        results: list    = []
        current_cg: dict = None
        current_cp: dict = None

        def _flush_cg(cg: dict) -> None:
            """Append cg to results if it has at least one uncovered bin."""
            if cg is None:
                return
            # Remove coverpoints that turned out to have no ZERO bins
            cg['uncovered_coverpoints'] = [
                cp for cp in cg['uncovered_coverpoints']
                if cp['uncovered_bins']
            ]
            if cg['uncovered_coverpoints']:
                results.append(cg)

        for line in lines:

            # ── TYPE section delimiter ─────────────────────────────────────
            # A TYPE line signals the end of the previous INSTANCE block and
            # the start of a new type-definition block (which we skip).
            if type_section_pat.match(line):
                _flush_cg(current_cg)
                current_cg = None
                current_cp = None
                continue

            # ── New covergroup instance ────────────────────────────────────
            m = instance_pat.match(line)
            if m:
                # Two consecutive INSTANCE lines (different instances of the
                # same type) also need the previous one flushed.
                _flush_cg(current_cg)

                raw_path = m.group(1).replace('\\', '').strip('/')
                cg_name  = raw_path.split('/')[-1]
                cg_pct   = float(m.group(2))

                current_cg = {
                    'covergroup':            cg_name,
                    'instance_path':         '/' + raw_path,
                    'coverage_pct':          cg_pct,
                    'uncovered_coverpoints': [],
                }
                current_cp = None
                continue

            # Lines outside any instance block are irrelevant
            if current_cg is None:
                continue

            # ── Coverpoint / Cross header ──────────────────────────────────
            m = coverpoint_pat.match(line)
            if m:
                current_cp = {
                    'name':           m.group(2),
                    'kind':           m.group(1),   # 'Coverpoint' or 'Cross'
                    'coverage_pct':   float(m.group(3)),
                    'uncovered_bins': [],
                }
                current_cg['uncovered_coverpoints'].append(current_cp)
                continue

            # Bin lines have no meaning without an active coverpoint context
            if current_cp is None:
                continue

            # ── ZERO bin ───────────────────────────────────────────────────
            m = zero_bin_pat.match(line)
            if m:
                current_cp['uncovered_bins'].append(m.group(1))

        # Flush the last instance after the loop completes
        _flush_cg(current_cg)

        return results

    except Exception as e:
        logging.error(f"parse_functional_coverage_holes failed: {e}")
        return []


def _read_source_lines(file_path: str) -> Optional[List[str]]:
    """
    Read all lines from a source file and return them as a list (1-indexed access
    via ``source_lines[line_num - 1]``).

    Returns ``None`` if the file cannot be read, so callers can fall back to
    printing line numbers only.  Lines are returned with trailing whitespace
    stripped but otherwise unmodified.
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as fh:
            return [line.rstrip() for line in fh.readlines()]
    except OSError as e:
        logging.warning(f"_read_source_lines: could not open {file_path}: {e}")
        return None


def _format_code_coverage_section(
    ucdb_path: Path,
    coverage_pct: float,
    simulator_path: Path,
) -> List[str]:
    """
    Build the code-coverage section of the hole report.

    Invokes ``vsim -viewcov`` to regenerate an XML report from the cumulative
    UCDB, then parses uncovered lines grouped by source file.  For each
    uncovered line the actual source code is included next to the line number
    so the reader does not need to cross-reference the RTL manually.

    Format per file::

        File: /path/to/sha1_core.v
          Line  248:   a_new  = H0_reg;
          Line  249:   b_new  = H1_reg;
          ...
        (3 uncovered lines in this file)

    If a source file cannot be read (e.g. path stored in the UCDB no longer
    exists on disk), the section falls back to printing line numbers only.

    Args:
        ucdb_path:      Path to the cumulative code-coverage UCDB.
        coverage_pct:   Final cumulative code coverage percentage.
        simulator_path: Path to the QuestaSim binary directory.

    Returns:
        List of text lines (without trailing newlines) to be joined into the
        report.  Never raises – errors are logged and reflected in the output.
    """
    lines: List[str] = [
        "CODE COVERAGE",
        "-" * 40,
        f"Final cumulative coverage: {coverage_pct:.2f}%",
        "",
    ]

    try:
        # Generate a fresh XML report from the cumulative UCDB.
        # Use a dedicated filename to avoid colliding with per-iteration reports.
        xml_path = ucdb_path.parent / f"{ucdb_path.stem}_hole_report.xml"
        command  = build_coverage_report_command(simulator_path, ucdb_path, xml_path)

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=str(ucdb_path.parent),
        )

        if result.returncode != 0 or not xml_path.exists():
            logging.error(
                f"vsim -viewcov failed (rc={result.returncode}) "
                f"while generating XML for hole report: {result.stderr[:300]}"
            )
            lines.append("  [Could not generate XML coverage report – check run.log]")
            lines.append("")
            return lines

        # Parse the XML; reuse the existing utility function.
        _, module_breakdown, uncovered_lines = parse_coverage_xml(xml_path)

        if not uncovered_lines:
            lines.append("  All lines covered.")
            lines.append("")
            return lines

        lines.append("UNCOVERED LINES")
        lines.append("")

        total_uncovered = 0
        for file_path, line_nums in sorted(uncovered_lines.items()):
            lines.append(f"  File: {file_path}")

            # Attempt to read the source file so we can show actual code.
            source_lines = _read_source_lines(file_path)

            for line_num in line_nums:
                if source_lines is not None:
                    # Guard against stale XML referencing a line beyond EOF
                    if 1 <= line_num <= len(source_lines):
                        source_text = source_lines[line_num - 1]
                        lines.append(f"    Line {line_num:>5}:  {source_text}")
                    else:
                        lines.append(f"    Line {line_num:>5}:  [line out of range]")
                else:
                    # Fallback: source file unreadable, print number only
                    lines.append(f"    Line {line_num:>5}")

            total_uncovered += len(line_nums)
            lines.append(f"  ({len(line_nums)} uncovered line(s) in this file)")
            lines.append("")

        lines.append(f"  Total uncovered lines: {total_uncovered}")
        lines.append("")

    except Exception as e:
        logging.error(f"_format_code_coverage_section failed unexpectedly: {e}")
        lines.append("  [Unexpected error generating code coverage section – check run.log]")
        lines.append("")

    return lines


def _format_functional_coverage_section(
    func_report_path: Path,
    coverage_pct: float,
) -> List[str]:
    """
    Build the functional-coverage section of the hole report.

    Parses the cumulative functional coverage text report and formats all
    uncovered bins using a three-level hierarchy:
    ``Covergroup → Coverpoint/Cross → bin``.

    Args:
        func_report_path: Path to ``coverage/cumulative_functional_coverage.txt``.
        coverage_pct:     Final cumulative functional coverage percentage.

    Returns:
        List of text lines (without trailing newlines) to be joined into the
        report.  Never raises – errors are logged and reflected in the output.
    """
    lines: List[str] = [
        "FUNCTIONAL COVERAGE",
        "-" * 40,
        f"Final cumulative coverage: {coverage_pct:.2f}%",
        "",
    ]

    try:
        holes = parse_functional_coverage_holes(func_report_path)

        if not holes:
            lines.append("  All bins covered.")
            lines.append("")
            return lines

        lines.append("UNCOVERED BINS")
        lines.append("")

        total_bins = 0
        for cg in holes:
            lines.append(
                f"  Covergroup: {cg['covergroup']}"
                f"  (instance: {cg['instance_path']},"
                f"  coverage: {cg['coverage_pct']:.2f}%)"
            )
            for cp in cg['uncovered_coverpoints']:
                lines.append(
                    f"    {cp['kind']}: {cp['name']}"
                    f"  ({cp['coverage_pct']:.2f}% covered)"
                )
                for bin_name in cp['uncovered_bins']:
                    lines.append(f"      bin: {bin_name}")
                    total_bins += 1
            lines.append("")

        lines.append(f"  Total uncovered bins: {total_bins}")
        lines.append("")

    except Exception as e:
        logging.error(f"_format_functional_coverage_section failed unexpectedly: {e}")
        lines.append("  [Unexpected error generating functional coverage section – check run.log]")
        lines.append("")

    return lines


def generate_coverage_hole_report(
    state: dict,
    simulator_path: Path,
) -> Optional[Path]:
    """
    Generate a plain-text coverage hole report and write it to
    ``<RUN_ID>/coverage_hole_report.txt``.

    The report is placed in the *parent* of the active work directory so that
    it sits alongside the ``code_cov/`` and ``func_cov/`` sub-directories:

        work/
        └── <RUN_ID>/
            ├── code_cov/
            ├── func_cov/
            └── coverage_hole_report.txt   ← this file

    The function is mode-aware:

    * **Single code-coverage mode** – writes a code-coverage section only.
    * **Single functional-coverage mode** – writes a functional-coverage
      section only.
    * **Combined mode** – writes both sections.  The code-coverage UCDB path
      is taken from ``state["code_coverage_summary"]`` (captured at phase
      transition); the functional coverage report is read from the Phase 2
      work directory.

    In all cases the function is silent about stages that achieved 100%
    coverage (those sections will state "All lines/bins covered").

    Args:
        state:           Final agent state dictionary as returned by LangGraph.
        simulator_path:  Path to the QuestaSim binary directory; used to invoke
                         ``vsim -viewcov`` for XML report generation.

    Returns:
        Absolute ``Path`` to the written report file, or ``None`` if the report
        could not be generated at all (errors are logged via the standard
        ``logging`` module).
    """
    try:
        config = state.get("config")
        if config is None:
            logging.error(
                "generate_coverage_hole_report: 'config' key missing from state"
            )
            return None

        work_dir    = Path(state["work_dir"])
        run_dir     = work_dir.parent          # …/RUN_ID/
        report_path = run_dir / "coverage_hole_report.txt"

        is_combined   = getattr(config, "combined_coverage_enabled", False)
        is_functional = state.get("functional_coverage_enabled", False)

        report_lines: List[str] = []

        # ── Header ────────────────────────────────────────────────────────
        report_lines += [
            "=" * 80,
            "COVERAGE HOLE REPORT",
            f"Design:    {state.get('design_name', 'unknown')}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 80,
            "",
        ]

        # ── Code coverage section ─────────────────────────────────────────
        # In combined mode the Phase 1 cumulative UCDB path is saved in
        # code_coverage_summary at the phase transition.
        # In single code-coverage mode it lives in cumulative_coverage_db.
        code_ucdb_path    = None
        code_coverage_pct = 0.0

        if is_combined:
            code_summary      = state.get("code_coverage_summary") or {}
            ucdb_str          = code_summary.get("cumulative_coverage_db")
            code_ucdb_path    = Path(ucdb_str) if ucdb_str else None
            code_coverage_pct = code_summary.get("cumulative_coverage", 0.0)
        elif not is_functional:
            # Pure code-coverage (single-mode) run
            ucdb_str          = state.get("cumulative_coverage_db")
            code_ucdb_path    = Path(ucdb_str) if ucdb_str else None
            code_coverage_pct = state.get("cumulative_coverage", 0.0)

        if code_ucdb_path and code_ucdb_path.exists():
            report_lines += _format_code_coverage_section(
                code_ucdb_path, code_coverage_pct, simulator_path
            )
        elif not is_functional:
            # Only emit the placeholder when a code-coverage stage was expected
            report_lines += [
                "CODE COVERAGE",
                "-" * 40,
                "  [No cumulative coverage database found]",
                "",
            ]

        # ── Functional coverage section ───────────────────────────────────
        if is_functional or is_combined:
            # The cumulative functional coverage report is always written to
            # this canonical path inside the func_cov work directory.
            func_report_path  = work_dir / "coverage" / "cumulative_functional_coverage.txt"
            func_coverage_pct = state.get("cumulative_coverage", 0.0)

            if func_report_path.exists():
                report_lines += _format_functional_coverage_section(
                    func_report_path, func_coverage_pct
                )
            else:
                report_lines += [
                    "FUNCTIONAL COVERAGE",
                    "-" * 40,
                    "  [No cumulative functional coverage report found]",
                    "",
                ]

        # ── Footer ────────────────────────────────────────────────────────
        report_lines += [
            "=" * 80,
            "END OF REPORT",
            "=" * 80,
        ]

        # ── Write ─────────────────────────────────────────────────────────
        report_content = "\n".join(report_lines) + "\n"
        with open(report_path, "w", encoding="utf-8") as fh:
            fh.write(report_content)

        logging.info(f"Coverage hole report written to: {report_path}")
        return report_path

    except Exception as e:
        logging.error(f"generate_coverage_hole_report failed: {e}")
        return None
