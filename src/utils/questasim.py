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


def parse_functional_coverage_text(report_path: Path) -> Dict:
    """
    Parse QuestaSim functional coverage text report.

    Extracts the full three-level hierarchy for uncovered bins:
    covergroup instance -> coverpoint/cross -> bin name.

    Also extracts the sample event (how/when the covergroup is sampled)
    so the LLM understands the conditions under which coverage is recorded.

    Args:
        report_path: Path to text coverage report

    Returns dict with 'total_coverage' and 'covergroups' list.
    Each covergroup has: name, instance_path, coverage, sample_event,
    uncovered_bins (list of {coverpoint, coverpoint_kind, bin_name} dicts).
    """
    if not report_path.exists():
        logging.error(f'Functional coverage report not found: {report_path}')
        return {'total_coverage': 0.0, 'covergroups': []}

    try:
        with open(report_path, 'r', encoding='utf-8', errors='ignore') as f:
            rlines = f.readlines()

        total_pat        = re.compile(r'TOTAL COVERGROUP COVERAGE:\s+([\d.]+)%')
        instance_pat     = re.compile(r' Covergroup instance\s+\\?/?([\w/\\]+)\s+([\d.]+)%')
        sample_pat       = re.compile(r'^\s+Sample\s+(?:event|type)\s*:\s*(.+)', re.IGNORECASE)
        coverpoint_pat   = re.compile(r'^    (Coverpoint|Cross)\s+(\w+)\s+([\d.]+)%')
        zero_bin_pat     = re.compile(r'^\s+bin\s+([\w\[\]<>,\*\-\.]+)\s+0\s+1\s+-\s+ZERO')
        type_section_pat = re.compile(r' TYPE ')

        total_coverage  = 0.0
        covergroups     = []
        current_cg      = None
        current_cp_name = None
        current_cp_kind = None

        def _flush_cg(cg):
            if cg is not None:
                covergroups.append(cg)

        for line in rlines:
            m = total_pat.search(line)
            if m:
                total_coverage = float(m.group(1))
                continue

            if type_section_pat.search(line):
                _flush_cg(current_cg)
                current_cg      = None
                current_cp_name = None
                current_cp_kind = None
                continue

            m = instance_pat.search(line)
            if m:
                _flush_cg(current_cg)
                raw_path = m.group(1).replace('\\', '').strip('/')
                cg_name  = raw_path.split('/')[-1]
                current_cg = {
                    'name':           cg_name,
                    'instance_path':  '/' + raw_path,
                    'coverage':       float(m.group(2)),
                    'sample_event':   None,
                    'uncovered_bins': [],
                }
                current_cp_name = None
                current_cp_kind = None
                continue

            if current_cg is None:
                continue

            m = sample_pat.match(line)
            if m and current_cg['sample_event'] is None:
                current_cg['sample_event'] = m.group(1).strip()
                continue

            m = coverpoint_pat.match(line)
            if m:
                current_cp_kind = m.group(1)
                current_cp_name = m.group(2)
                continue

            m = zero_bin_pat.match(line)
            if m and current_cp_name is not None:
                current_cg['uncovered_bins'].append({
                    'coverpoint':      current_cp_name,
                    'coverpoint_kind': current_cp_kind or 'Coverpoint',
                    'bin_name':        m.group(1),
                })

        _flush_cg(current_cg)

        return {
            'total_coverage': total_coverage,
            'covergroups':    covergroups,
        }

    except Exception as e:
        logging.error(f'Functional coverage parsing failed: {e}')
        return {'total_coverage': 0.0, 'covergroups': [], 'error': str(e)}
