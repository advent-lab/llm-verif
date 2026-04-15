"""QuestaSim simulator adapter implementation.

This adapter provides QuestaSim-specific implementations for compilation,
simulation, and coverage parsing. QuestaSim is a commercial HDL simulator
that uses .ucdb (Universal Coverage Database) files and XML reports.
"""

import re
import subprocess
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Tuple

from .base import SimulatorAdapter, CoverageResult
from ..utils.questasim import (
    build_vlog_command,
    build_vsim_command,
    build_vcover_merge_command,
    check_questasim_success
)


class QuestasimAdapter(SimulatorAdapter):
    """QuestaSim simulator adapter.

    Implements the SimulatorAdapter interface for Mentor Graphics QuestaSim.
    Uses vlog for compilation, vsim for simulation, and vcover for coverage
    database merging.
    """

    # Lines matching these patterns are QuestaSim vlog (compile) boilerplate
    _COMPILE_BOILERPLATE_PATTERNS = [
        re.compile(r"^Questa Intel"),              # version banner
        re.compile(r"^Start time:"),               # timestamp
        re.compile(r"^vlog\s"),                    # echoed command with long paths
        re.compile(r"^-- Compiling module\s"),     # per-module compilation status
        re.compile(r"^Top level modules:"),         # top-level header
        re.compile(r"^\t\w"),                       # indented module name under "Top level modules:"
        re.compile(r"^End time:"),                 # end timestamp
    ]

    # Lines matching these patterns are QuestaSim vsim (simulate) boilerplate
    _BOILERPLATE_PATTERNS = [
        re.compile(r"^#\s*//"),                          # copyright / license banner
        re.compile(r"^#\s*Reading pref\.tcl"),            # QuestaSim preamble
        re.compile(r"^#\s*\d{4}\.\d"),                   # version echo e.g. "# 2023.3"
        re.compile(r"^#\s*Loading sv_std"),               # Loading sv_std.std
        re.compile(r"^#\s*Loading work\."),               # Loading work.*
        re.compile(r"^#\s*coverage exclude"),             # coverage commands
        re.compile(r"^#\s*coverage save"),                # coverage save commands
        re.compile(r"^#\s*run -all"),                     # simulation start command
        re.compile(r"^#\s*Saving coverage database on exit"),
        re.compile(r"^#\s*\*\* Note: \(vsim-8009\)"),    # "Loading existing optimized design"
        re.compile(r"^#\s*\*\* Note: \(vsim-3812\)"),    # "Design is being optimized"
        re.compile(r"^#\s*\*\* Note: \(vsim-12126\)"),   # "Error and warning message counts"
    ]

    def _filter_by_patterns(self, output: str, patterns: list) -> str:
        """Strip lines matching the given patterns and collapse excess blank lines."""
        if not output:
            return output

        filtered_lines = []
        for line in output.splitlines():
            stripped = line.strip()
            if any(p.match(stripped) for p in patterns):
                continue
            filtered_lines.append(line)

        # Collapse runs of 3+ blank lines into a single blank line
        result_lines = []
        blank_count = 0
        for line in filtered_lines:
            if line.strip() == "":
                blank_count += 1
                if blank_count <= 1:
                    result_lines.append(line)
            else:
                blank_count = 0
                result_lines.append(line)

        return "\n".join(result_lines)

    def filter_compile_output(self, output: str) -> str:
        """Strip QuestaSim vlog boilerplate from compiler output.

        Removes the version banner, echoed command (with long absolute paths),
        per-module ``-- Compiling module`` lines, and timestamps.  Keeps
        ``** Error``, ``** Warning``, and the final ``Errors: N, Warnings: N``
        summary.
        """
        return self._filter_by_patterns(output, self._COMPILE_BOILERPLATE_PATTERNS)

    def filter_sim_output(self, output: str) -> str:
        """Strip QuestaSim vsim boilerplate from simulator output.

        Removes copyright banners, loading messages, coverage commands, and
        informational notes that waste LLM input tokens.  Keeps errors,
        warnings, $finish, timing, seed, and run headers.
        """
        return self._filter_by_patterns(output, self._BOILERPLATE_PATTERNS)

    def compile(self, testbench_path: Path, design_files: List[Path],
                work_dir: Path, timeout: int,
                functional_coverage: bool = False) -> Dict[str, Any]:
        """Compile testbench using QuestaSim's vlog compiler.

        Args:
            testbench_path: Path to testbench SystemVerilog file
            design_files: List of design RTL files
            work_dir: Working directory (must contain 'work' library)
            timeout: Compilation timeout in seconds

        Returns:
            Compilation result dictionary with success status and outputs
        """
        try:
            # Build vlog command — functional_coverage=True adds +cover=sbfec
            command = build_vlog_command(self.simulator_path, testbench_path, design_files,
                                               functional_coverage=functional_coverage)

            logging.info(f"QuestaSim compile: {' '.join(str(c) for c in command)}")

            # Execute compilation
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(work_dir)  # Run in work directory for work library
            )

            # Check success by parsing output
            success = check_questasim_success(result.stdout)

            return {
                "success": success,
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "log_path": ""  # Log saving handled by tool layer
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Compilation timeout after {timeout}s"
            }
        except Exception as e:
            logging.error(f"QuestaSim compilation error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def simulate(self, testbench_name: str, num_runs: int,
                 work_dir: Path, iteration: int, timeout: int) -> Dict[str, Any]:
        """Run QuestaSim simulation with coverage collection.

        QuestaSim generates separate .ucdb files for each run, which are then
        merged into a single coverage database.

        Args:
            testbench_name: Name of testbench module
            num_runs: Number of simulation runs with different random seeds
            work_dir: Working directory
            iteration: Current iteration number
            timeout: Timeout per simulation run in seconds

        Returns:
            Simulation result with coverage database path
        """
        try:
            coverage_dir = work_dir / "coverage"
            coverage_dir.mkdir(parents=True, exist_ok=True)

            ucdb_files = []
            all_stdout = []
            all_stderr = []

            # Run multiple simulations with different random seeds
            for run_idx in range(num_runs):
                ucdb_filename = f"iter_{iteration}_run_{run_idx}.ucdb"
                ucdb_abs_path = coverage_dir / ucdb_filename
                # Use relative path from work_dir for command (avoids path confusion)
                ucdb_rel_path = Path("coverage") / ucdb_filename

                # Build vsim command with relative path
                command = build_vsim_command(self.simulator_path, ucdb_rel_path)

                logging.info(f"QuestaSim simulation run {run_idx+1}/{num_runs}")

                try:
                    result = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        cwd=str(work_dir)
                    )

                    all_stdout.append(f"=== Run {run_idx} ===\n{result.stdout}")
                    all_stderr.append(result.stderr)

                    # Check if this run succeeded and UCDB file was created
                    if check_questasim_success(result.stdout) and ucdb_abs_path.exists():
                        ucdb_files.append(ucdb_abs_path)
                    else:
                        logging.warning(f"QuestaSim run {run_idx} failed")

                except subprocess.TimeoutExpired:
                    logging.warning(f"QuestaSim run {run_idx} timed out")
                    continue

            if not ucdb_files:
                return {
                    "success": False,
                    "error": "All simulation runs failed"
                }

            # Merge coverage databases if multiple runs succeeded
            if len(ucdb_files) > 1:
                merged_ucdb = coverage_dir / f"iter_{iteration}.ucdb"
                merge_command = build_vcover_merge_command(
                    self.simulator_path, merged_ucdb, ucdb_files
                )

                logging.info(f"Merging {len(ucdb_files)} coverage databases")
                result = subprocess.run(merge_command, capture_output=True, text=True)

                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Coverage merge failed: {result.stderr}"
                    }

                coverage_db_path = merged_ucdb
            else:
                coverage_db_path = ucdb_files[0]

            return {
                "success": True,
                "stdout": "\n\n".join(all_stdout),
                "stderr": "\n".join(all_stderr),
                "coverage_db_path": str(coverage_db_path),
                "num_runs_completed": len(ucdb_files)
            }

        except Exception as e:
            logging.error(f"QuestaSim simulation error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def parse_coverage(self, coverage_db_path: Path) -> CoverageResult:
        """Parse QuestaSim coverage database (.ucdb).

        Generates XML report from .ucdb file and parses it to extract
        module-level coverage and uncovered line numbers.

        Args:
            coverage_db_path: Path to .ucdb coverage database

        Returns:
            CoverageResult with normalized coverage data

        Raises:
            FileNotFoundError: If coverage database doesn't exist
            RuntimeError: If XML generation or parsing fails
        """
        if not coverage_db_path.exists():
            raise FileNotFoundError(f"Coverage database not found: {coverage_db_path}")

        # Generate XML report from UCDB
        xml_path = coverage_db_path.parent / f"{coverage_db_path.stem}_report.xml"

        from ..utils.questasim import build_coverage_report_command

        command = build_coverage_report_command(
            self.simulator_path, coverage_db_path, xml_path
        )

        logging.info("Generating QuestaSim coverage report")
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=str(coverage_db_path.parent)
        )

        if result.returncode != 0:
            raise RuntimeError(f"Coverage report generation failed: {result.stderr}")

        # Parse XML report
        total_coverage, module_breakdown, uncovered_lines = self._parse_coverage_xml(xml_path)

        return CoverageResult(
            total_coverage=total_coverage,
            breakdown=module_breakdown,
            uncovered_lines=uncovered_lines
        )

    def _parse_coverage_xml(self, xml_path: Path) -> Tuple[float, Dict[str, float], Dict[str, List[int]]]:
        """Parse QuestaSim XML coverage report.

        Args:
            xml_path: Path to XML coverage report

        Returns:
            Tuple of (total_coverage, module_breakdown, uncovered_lines)
        """
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            total_active = 0
            total_hits = 0
            module_breakdown = {}
            uncovered_lines = {}

            # Parse each design unit
            for du_data in root.findall('.//DuData'):
                du_name = du_data.get('du')

                # Skip testbench from coverage (focus on DUT)
                if du_name == 'tb_llm':
                    continue

                # Get file path
                file_map = du_data.find('.//fileMap')
                file_path = file_map.get('path') if file_map is not None else "unknown"

                # Get statement coverage stats
                statements = du_data.find('statements')
                if statements is not None:
                    active = int(statements.get('active', 0))
                    hits = int(statements.get('hits', 0))
                    percent = float(statements.get('percent', 0.0))

                    total_active += active
                    total_hits += hits
                    module_breakdown[du_name] = percent

                    # Extract uncovered line numbers
                    uncovered = []
                    for stmt in du_data.findall('.//stmt'):
                        if stmt.get('hits') == '0':
                            line_num = int(stmt.get('ln'))
                            uncovered.append(line_num)

                    if uncovered:
                        uncovered_lines[file_path] = sorted(uncovered)

            # Calculate total coverage
            total_coverage = (total_hits / total_active * 100.0) if total_active > 0 else 0.0

            return round(total_coverage, 2), module_breakdown, uncovered_lines

        except (ET.ParseError, FileNotFoundError) as e:
            logging.error(f"QuestaSim coverage XML parsing failed: {e}")
            return 0.0, {}, {}

    def merge_cumulative_coverage(self, new_ucdb: Path, cumulative_ucdb: Path) -> Path:
        """Merge new iteration coverage with cumulative coverage database.

        If cumulative_ucdb doesn't exist, the new_ucdb becomes the cumulative.
        Otherwise, merges both into a new cumulative database.

        Args:
            new_ucdb: Path to new iteration's coverage database
            cumulative_ucdb: Path to cumulative coverage database

        Returns:
            Path to the updated cumulative coverage database

        Raises:
            RuntimeError: If merge operation fails
        """
        if not new_ucdb.exists():
            raise FileNotFoundError(f"New coverage database not found: {new_ucdb}")

        # If no cumulative exists yet, copy new as cumulative
        if not cumulative_ucdb.exists():
            import shutil
            shutil.copy(new_ucdb, cumulative_ucdb)
            logging.info(f"Initialized cumulative coverage: {cumulative_ucdb}")
            return cumulative_ucdb

        # Merge new coverage with cumulative
        # Create temp file for merged result, then replace cumulative
        temp_merged = cumulative_ucdb.parent / "cumulative_temp.ucdb"

        merge_command = build_vcover_merge_command(
            self.simulator_path, temp_merged, [cumulative_ucdb, new_ucdb]
        )

        logging.info(f"Merging iteration coverage into cumulative database")
        result = subprocess.run(merge_command, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Cumulative coverage merge failed: {result.stderr}")

        # Replace cumulative with merged result
        import shutil
        shutil.move(temp_merged, cumulative_ucdb)
        logging.info(f"Updated cumulative coverage: {cumulative_ucdb}")

        return cumulative_ucdb
    
    def cleanup(self) -> None:
        """Clean up QuestaSim-specific files.

        QuestaSim manages its own work library, so minimal cleanup is needed.
        This method is required by the SimulatorAdapter base class.
        """
        # QuestaSim cleanup is typically not needed as it manages work/ library
        # This method exists to satisfy the abstract base class requirement
        pass


# MODULE-LEVEL FUNCTION (outside the class)
def generate_functional_coverage_report(simulator_path: Path, ucdb_path: Path, 
                                       output_txt: Path) -> bool:
    """
    Generate text-based functional coverage report.
    
    Args:
        simulator_path: Path to simulator binaries
        ucdb_path: Path to coverage database
        output_txt: Path to output text file
    
    Returns:
        True if successful, False otherwise
    """
    try:
        cmd = [
            str(simulator_path / "vcover"),
            "report",
            "-details",
            "-output", str(output_txt),
            str(ucdb_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return result.returncode == 0 and output_txt.exists()
    
    except Exception as e:
        logging.error(f"Functional coverage report generation failed: {e}")
        return False
