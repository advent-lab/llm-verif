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
                        incdir_files: List[Path] = None,
                        functional_coverage: bool = False) -> List[List[str]]:
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

    cover_flag = "+cover=sbfec" if functional_coverage else "+cover=s"

    commands: List[List[str]] = []
    vlog = str(simulator_path / "vlog")

    if v_files:
        commands.append([vlog, cover_flag] + incdirs + [str(f) for f in v_files])
    if sv_files:
        commands.append([vlog, "-sv", cover_flag] + incdirs + [str(f) for f in sv_files])

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

def build_functional_coverage_report_command(
    simulator_path: Path, ucdb: Path, report_path: Path
) -> List[str]:
    """Build vcover report command for functional (covergroup) coverage."""
    return [
        str(simulator_path / "vcover"),
        "report",
        "-details",
        "-output", str(report_path),
        str(ucdb)
    ]


def parse_functional_coverage_text(report_path: Path) -> Dict:
    """
    Parse QuestaSim functional coverage text report.

    Uses a line-by-line state machine so each uncovered bin is enriched with
    its parent coverpoint name, coverpoint kind (Coverpoint or Cross), and
    the covergroup sample event.

    Returns:
        {
            'total_coverage': 90.59,
            'covergroups': [
                {
                    'name':          'cg_ctrl_inst',
                    'instance_path': '/tb_llm/cg_ctrl_inst',
                    'coverage':      95.83,
                    'sample_event':  '@(posedge clk)',
                    'uncovered_bins': [
                        {
                            'coverpoint':      'cp_cmd_transitions',
                            'coverpoint_kind': 'Coverpoint',
                            'bin_name':        'init_to_next',
                        }
                    ]
                }
            ]
        }
    """
    if not report_path.exists():
        logging.error(f"Functional coverage report not found: {report_path}")
        return {'total_coverage': 0.0, 'covergroups': []}

    try:
        with open(report_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        total_pat      = re.compile(r'TOTAL COVERGROUP COVERAGE:\s+([\d.]+)%')
        instance_pat   = re.compile(
            r'^ Covergroup instance\s+\\?/?(\w[\w/\\]*)\s+([\d.]+)%'
        )
        sample_pat     = re.compile(
            r'\s+Sample\s+(?:event|type)\s*:\s*(.+)', re.IGNORECASE
        )
        coverpoint_pat = re.compile(
            r'^    (Coverpoint|Cross)\s+(\w+)\s+([\d.]+)%'
        )
        zero_bin_pat   = re.compile(
            r'^\s+bin\s+([\w\[\]<>,\*\-\.]+)\s+0\s+1\s+-\s+ZERO'
        )
        type_pat       = re.compile(r'^ TYPE ')

        total_coverage = 0.0
        covergroups    = []
        current_cg     = None
        current_cp     = None

        def _flush_cg(cg):
            if cg is not None:
                covergroups.append(cg)

        for line in lines:
            m = total_pat.search(line)
            if m:
                total_coverage = float(m.group(1))
                continue

            if type_pat.match(line):
                _flush_cg(current_cg)
                current_cg = None
                current_cp = None
                continue

            m = instance_pat.match(line)
            if m:
                _flush_cg(current_cg)
                raw = m.group(1).replace('\\', '').strip('/')
                current_cg = {
                    'name':           raw.split('/')[-1],
                    'instance_path':  '/' + raw,
                    'coverage':       float(m.group(2)),
                    'sample_event':   None,
                    'uncovered_bins': [],
                }
                current_cp = None
                continue

            if current_cg is None:
                continue

            m = sample_pat.match(line)
            if m and current_cg['sample_event'] is None:
                current_cg['sample_event'] = m.group(1).strip()
                continue

            m = coverpoint_pat.match(line)
            if m:
                current_cp = {
                    'name':     m.group(2),
                    'kind':     m.group(1),
                    'coverage': float(m.group(3)),
                }
                continue

            if current_cp is None:
                continue

            m = zero_bin_pat.match(line)
            if m:
                current_cg['uncovered_bins'].append({
                    'coverpoint':      current_cp['name'],
                    'coverpoint_kind': current_cp['kind'],
                    'bin_name':        m.group(1),
                })

        _flush_cg(current_cg)

        return {
            'total_coverage': total_coverage,
            'covergroups':    covergroups,
        }

    except Exception as e:
        logging.error(f"Functional coverage parsing failed: {e}")
        return {'total_coverage': 0.0, 'covergroups': [], 'error': str(e)}


def inject_stimulus_into_template(
    template_path: Path,
    stimulus_path: Path,
    output_path: Path,
) -> Path:
    """Inject agent-generated stimulus body into a functional coverage testbench template.

    The template must contain a marked placeholder region, e.g.:

        // STIMULUS_BEGIN
        initial begin
            $finish;
        end
        // STIMULUS_END

    The stimulus file written by the agent contains ONLY the body lines of the
    initial block — no ``initial begin``, no ``$finish;``, no ``end`` wrapper,
    no module wrapper.  The framework wraps the body and replaces the marked
    region automatically.

    Args:
        template_path: Path to the user-provided testbench template (.sv).
        stimulus_path: Path to the agent's stimulus body file.
        output_path:   Destination for the patched testbench (.sv).

    Returns:
        output_path — the patched testbench ready for compilation.

    Raises:
        ValueError: If the template does not contain the required markers.
    """
    template_text = template_path.read_text(encoding='utf-8')
    stimulus_body = stimulus_path.read_text(encoding='utf-8').strip()

    # Match the entire stimulus marker block, capturing leading whitespace on
    # the opening line. Accepts both orderings:
    #   // STIMULUS_BEGIN ... // STIMULUS_END  (canonical)
    #   // BEGIN_STIMULUS  ... // END_STIMULUS (legacy)
    pattern = re.compile(
        r'^([ \t]*)//\s*(?:STIMULUS_BEGIN|BEGIN_STIMULUS)\b.*?//\s*(?:STIMULUS_END|END_STIMULUS)\b',
        re.MULTILINE | re.DOTALL,
    )

    match = pattern.search(template_text)
    if not match:
        raise ValueError(
            f"Template '{template_path.name}' is missing stimulus injection markers. "
            "Add either '// STIMULUS_BEGIN ... // STIMULUS_END' or "
            "'// BEGIN_STIMULUS ... // END_STIMULUS' to delimit the empty "
            "initial block in your functional coverage template."
        )

    indent = match.group(1)        # e.g. "    " (module-level indent)
    body_indent = indent + "    "  # one level deeper for stimulus lines

    replacement_lines = [
        f"{indent}// STIMULUS_BEGIN",
        f"{indent}initial begin",
    ]
    for line in stimulus_body.splitlines():
        if line.strip():
            replacement_lines.append(f"{body_indent}{line}")
        else:
            replacement_lines.append("")
    replacement_lines.append(f"{body_indent}$finish;")
    replacement_lines.append(f"{indent}end")
    replacement_lines.append(f"{indent}// STIMULUS_END")

    patched = pattern.sub("\n".join(replacement_lines), template_text)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(patched, encoding='utf-8')
    logging.info(f"Stimulus injected: {stimulus_path.name} → {output_path.name}")
    return output_path


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
                module_breakdown[file_path] = percent

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


# ── UVM command builders ───────────────────────────────────────────────────
# UVM 3-step compile flow:
#   1. vlib work  +  vlib uvm_lib
#   2. vlog -sv -work uvm_lib +incdir+$UVM_HOME/src uvm_pkg.sv
#   3. vmap mtiUvm uvm_lib  (redirect QuestaSim's built-in 1.1d → our 1.2)
#   4. vlog -sv -mfcu -L uvm_lib -f filelist.f
#   5. vopt +acc <Top> -L uvm_lib -o opt_top +cover=bcestf
#
# The vmap step is critical: without it QuestaSim auto-loads mtiUvm (1.1d)
# alongside our uvm_lib (1.2) causing factory registration failures (INVTST).

def build_uvm_vlib_uvm_command(simulator_path: Path) -> List[str]:
    """Build vlib command to create a dedicated UVM library."""
    return [str(simulator_path / "vlib"), "uvm_lib"]


def build_uvm_vlog_uvm_command(simulator_path: Path, uvm_home: str) -> List[str]:
    """Compile UVM 1.2 from source into ``uvm_lib``.

    Compiled from source rather than using the pre-compiled library because
    QuestaSim 2025.x added stricter type checks that reject classes compiled
    with older versions (vsim-12460, vsim-8754).
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

    QuestaSim's modelsim.ini maps mtiUvm → uvm-1.1d and LibrarySearchPath
    auto-loads mtiUvm during elaboration. Without this vmap, both UVM 1.1d
    and our UVM 1.2 are loaded, causing factory registration to silently
    fail (INVTST).
    """
    return [str(simulator_path / "vmap"), "mtiUvm", "uvm_lib"]


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
    do_script = f"coverage save -onexit {ucdb_path}; run -all; quit"
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
