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
    build_vlog_commands,
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
                work_dir: Path, timeout: int) -> Dict[str, Any]:
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
            # Build separate vlog commands for .v (Verilog) and .sv (SystemVerilog)
            # files.  Legacy .v files may use identifiers like ``return`` that
            # clash with SystemVerilog reserved keywords.
            commands = build_vlog_commands(self.simulator_path, testbench_path, design_files)

            all_stdout = []
            all_stderr = []
            last_returncode = 0

            for command in commands:
                logging.info(f"QuestaSim compile: {' '.join(str(c) for c in command)}")

                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(work_dir)  # Run in work directory for work library
                )

                all_stdout.append(result.stdout)
                all_stderr.append(result.stderr)
                last_returncode = result.returncode

                # Fail fast: if this pass has errors, stop immediately
                if not check_questasim_success(result.stdout):
                    return {
                        "success": False,
                        "return_code": result.returncode,
                        "stdout": "\n".join(all_stdout),
                        "stderr": "\n".join(all_stderr),
                        "log_path": ""
                    }

            combined_stdout = "\n".join(all_stdout)
            combined_stderr = "\n".join(all_stderr)
            success = check_questasim_success(all_stdout[-1]) if all_stdout else False

            return {
                "success": success,
                "return_code": last_returncode,
                "stdout": combined_stdout,
                "stderr": combined_stderr,
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
            timed_out_runs = 0

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

                    run_stdout = result.stdout

                    # Fallback: when vsim fails during optimization/loading,
                    # stdout is empty but errors are in the transcript file.
                    if not run_stdout.strip():
                        transcript_path = work_dir / "transcript"
                        if transcript_path.exists():
                            try:
                                run_stdout = transcript_path.read_text()
                            except OSError:
                                pass

                    all_stdout.append(f"=== Run {run_idx} ===\n{run_stdout}")
                    all_stderr.append(result.stderr)

                    # Check if this run succeeded and UCDB file was created
                    if check_questasim_success(result.stdout) and ucdb_abs_path.exists():
                        ucdb_files.append(ucdb_abs_path)
                    else:
                        logging.warning(f"QuestaSim run {run_idx} failed")

                except subprocess.TimeoutExpired:
                    timed_out_runs += 1
                    all_stdout.append(f"=== Run {run_idx} ===\nTIMEOUT: Simulation exceeded {timeout}s limit")
                    logging.warning(f"QuestaSim run {run_idx} timed out")
                    continue

            if not ucdb_files:
                if timed_out_runs == num_runs:
                    error_msg = f"All {num_runs} simulation runs timed out (limit: {timeout}s). The testbench likely has an infinite loop or excessively long execution."
                elif timed_out_runs > 0:
                    error_msg = f"All simulation runs failed ({timed_out_runs}/{num_runs} timed out, limit: {timeout}s)"
                else:
                    error_msg = "All simulation runs failed"
                return {
                    "success": False,
                    "error": error_msg,
                    "stdout": f"{all_stdout[0]}\n\n(All {len(all_stdout)} runs failed with the same error)" if all_stdout else "",
                    "stderr": all_stderr[0] if all_stderr else "",
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

            result = {
                "success": True,
                "stdout": "\n\n".join(all_stdout),
                "stderr": "\n".join(all_stderr),
                "coverage_db_path": str(coverage_db_path),
                "num_runs_completed": len(ucdb_files)
            }
            if timed_out_runs > 0:
                result["warning"] = f"{timed_out_runs}/{num_runs} runs timed out (limit: {timeout}s)"
            return result

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

    @staticmethod
    def cleanup(work_dir: Path) -> None:
        """Clean up QuestaSim-specific files.

        Removes:
        - work/ library directory
        - transcript file

        Args:
            work_dir: Working directory containing QuestaSim artifacts
        """
        import shutil

        try:
            # Remove work library
            work_lib = work_dir / "work"
            if work_lib.exists():
                shutil.rmtree(work_lib, ignore_errors=True)
                logging.info(f"Cleaned up QuestaSim work library: {work_lib}")

            # Remove transcript
            transcript = work_dir / "transcript"
            if transcript.exists():
                transcript.unlink()
                logging.info(f"Cleaned up QuestaSim transcript: {transcript}")

        except Exception as e:
            logging.warning(f"QuestaSim cleanup error: {e}")
