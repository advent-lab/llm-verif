import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple, Dict
import re
import logging
import os

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

def build_vsim_command(simulator_path: Path, ucdb_path: Path) -> List[str]:
    """Build vsim simulation command with coverage collection."""
    do_script = f"coverage exclude -du tb_llm;coverage save -onexit {ucdb_path};run -all;exit;"
    return [
        str(simulator_path / "vsim"),
        "work.tb_llm",  # Work library + module name
        "-coverage",
        "-sv_seed", "random",
        "-c",  # Command-line mode
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

## ── UVM Command Builders ─────────────────────────────────────────────────────

def build_uvm_vlib_uvm_command(simulator_path: Path) -> List[str]:
    """Build vlib command to create a dedicated UVM library."""
    return [str(simulator_path / "vlib"), "uvm_lib"]


def build_uvm_vlog_uvm_command(simulator_path: Path, uvm_home: str) -> List[str]:
    """Build vlog command to compile UVM 1.2 into a dedicated library.

    Compiles ``uvm_pkg`` into ``uvm_lib`` (not ``work``) so that it
    mirrors QuestaSim's precompiled ``-L uvm`` flow.  When UVM and the
    user's test class live in the same ``work`` library, factory
    registration silently fails.
    """
    return [
        str(simulator_path / "vlog"),
        "-sv",
        "-work", "uvm_lib",
        "+incdir+" + uvm_home + "/src",
        uvm_home + "/src/uvm_pkg.sv",
    ]


def build_uvm_vlog_design_command(simulator_path: Path, filelist: Path, uvm_home: str) -> List[str]:
    """Build vlog command to compile design + testbench files with ``-mfcu``.

    Runs after UVM 1.2 has been compiled into ``uvm_lib``.  Uses
    ``-L uvm_lib`` so that ``import uvm_pkg::*`` resolves from the
    separate library — identical to QuestaSim's ``-L uvm`` flow.
    """
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