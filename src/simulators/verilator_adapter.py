"""Verilator simulator adapter implementation.

This adapter provides Verilator-specific implementations for compilation,
simulation, and coverage parsing. Verilator is an open-source compile-to-C++
simulator that uses .dat coverage files and LCOV .info format.
"""

import subprocess
import logging
import re
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple

from .base import SimulatorAdapter, CoverageResult


class VerilatorAdapter(SimulatorAdapter):
    """Verilator simulator adapter.

    Implements the SimulatorAdapter interface for Verilator open-source simulator.
    Verilator compiles Verilog to C++, then compiles to a binary. Coverage is
    collected in .dat files (binary format) and converted to LCOV .info (text format).
    """

    def compile(self, testbench_path: Path, design_files: List[Path],
                work_dir: Path, timeout: int) -> Dict[str, Any]:
        """Compile testbench using Verilator.

        Verilator compiles Verilog/SystemVerilog to C++, then compiles to executable.
        The binary is generated in obj_dir/ subdirectory.

        Args:
            testbench_path: Path to testbench SystemVerilog file
            design_files: List of design RTL files
            work_dir: Working directory for compilation
            timeout: Compilation timeout in seconds

        Returns:
            Compilation result dictionary with success status
        """
        try:
            # Build Verilator compilation command
            command = [
                str(self.simulator_path / "verilator"),
                "--binary",              # Generate standalone executable
                "-j", "4",               # Parallel compilation (4 threads)
                "--coverage-line",       # Enable line-level coverage
                "-Wno-fatal",           # Don't treat warnings as fatal errors
                "--Mdir", str(work_dir / "obj_dir"),  # Output directory
                str(testbench_path)
            ] + [str(f) for f in design_files]

            logging.info(f"Verilator compile: {' '.join(command)}")

            # Setup environment for Verilator compilation
            # Load required modules for HPC environment (ASU SOL specific)
            env = os.environ.copy()

            # Check for environment module system availability
            module_system_available = os.path.exists("/etc/profile.d/modules.sh")

            if module_system_available:
                # Source module environment and load required modules
                # GCC 10.3.0 and ccache are required for Verilator C++ compilation
                module_setup = """
source /etc/profile.d/modules.sh
module load gcc-10.3.0-gcc-11.2.0 || echo "WARNING: GCC module not loaded"
module load ccache-4.8.2-gcc-11.2.0 || echo "WARNING: ccache module not loaded"
module list 2>&1 | grep -E "(gcc|ccache)" || echo "WARNING: Required modules may not be loaded"
"""
                logging.info("Loading HPC modules for Verilator compilation")
            else:
                module_setup = "# No module system detected, using system compilers\n"
                logging.warning("Module system not found, attempting compilation with system tools")

            # Execute compilation with bash to load modules
            full_command = f"{module_setup}\n{' '.join(command)}"
            result = subprocess.run(
                ["bash", "-c", full_command],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(work_dir),
                env=env
            )

            # Check for Verilator errors: %Error: or %Fatal:
            has_error = self._check_errors(result.stdout + result.stderr)
            success = not has_error and result.returncode == 0

            # Verify binary was created
            binary_pattern = work_dir / "obj_dir" / "V*"
            created_binaries = list(work_dir.glob("obj_dir/V*"))
            if success and not any(b.is_file() and b.stat().st_mode & 0o111 for b in created_binaries):
                logging.error("Verilator compilation reported success but no executable binary found")
                success = False

            if not success:
                error_msg = self._extract_error_message(result.stdout + result.stderr)
                logging.error(f"Verilator compilation failed: {error_msg}")

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
            logging.error(f"Verilator compilation error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def simulate(self, testbench_name: str, num_runs: int,
                 work_dir: Path, iteration: int, timeout: int) -> Dict[str, Any]:
        """Run Verilator simulation by executing compiled binary.

        Unlike QuestaSim, Verilator generates a standalone executable that we run
        directly. Coverage accumulates to a single .dat file across all runs.

        Args:
            testbench_name: Name of testbench module (e.g., "tb_llm")
            num_runs: Number of simulation runs
            work_dir: Working directory
            iteration: Current iteration number
            timeout: Timeout per simulation run in seconds

        Returns:
            Simulation result with coverage database path
        """
        try:
            coverage_dir = work_dir / "coverage"
            coverage_dir.mkdir(parents=True, exist_ok=True)

            # Coverage accumulates to single .dat file
            coverage_dat = coverage_dir / f"iter_{iteration}.dat"

            # Compiled binary location
            binary = work_dir / "obj_dir" / f"V{testbench_name}"

            if not binary.exists():
                # Try to find any Verilator binary in obj_dir
                binaries = list((work_dir / "obj_dir").glob("V*"))
                executable_binaries = [b for b in binaries if b.is_file() and b.stat().st_mode & 0o111]

                if executable_binaries:
                    actual_binary = executable_binaries[0]
                    logging.warning(f"Expected binary {binary.name} not found, using {actual_binary.name}")
                    binary = actual_binary
                else:
                    return {
                        "success": False,
                        "error": f"Compiled binary not found: {binary}. "
                               f"Expected Verilator to create executable in obj_dir/. "
                               f"Ensure testbench module name matches '{testbench_name}'."
                    }

            logging.info(f"Using Verilator binary: {binary}")

            all_stdout = []
            all_stderr = []
            successful_runs = 0
            timed_out_runs = 0

            # Run simulation multiple times (coverage accumulates)
            for run_idx in range(num_runs):
                # Command to run the executable with coverage output
                command = [
                    str(binary),
                    f"+verilator+coverage+file+{coverage_dat}"
                ]

                logging.info(f"Verilator simulation run {run_idx+1}/{num_runs}")

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

                    # Check if simulation completed (no fatal errors)
                    if result.returncode == 0:
                        successful_runs += 1
                    else:
                        logging.warning(f"Verilator run {run_idx} failed with code {result.returncode}")

                except subprocess.TimeoutExpired:
                    timed_out_runs += 1
                    all_stdout.append(f"=== Run {run_idx} ===\nTIMEOUT: Simulation exceeded {timeout}s limit")
                    logging.warning(f"Verilator run {run_idx} timed out")
                    continue

            if successful_runs == 0:
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

            # Verify coverage file was created
            if not coverage_dat.exists():
                return {
                    "success": False,
                    "error": f"Coverage file not generated: {coverage_dat}. "
                           f"Completed {successful_runs}/{num_runs} simulation runs. "
                           f"Coverage may not have been enabled during compilation."
                }

            # Check coverage file size
            if coverage_dat.stat().st_size == 0:
                logging.warning(f"Coverage file {coverage_dat} is empty")
                return {
                    "success": False,
                    "error": f"Coverage file generated but empty: {coverage_dat}"
                }

            logging.info(f"Verilator simulation complete: {successful_runs}/{num_runs} runs succeeded")
            logging.info(f"Coverage data saved to: {coverage_dat} ({coverage_dat.stat().st_size} bytes)")

            result = {
                "success": True,
                "stdout": "\n\n".join(all_stdout),
                "stderr": "\n".join(all_stderr),
                "coverage_db_path": str(coverage_dat),
                "num_runs_completed": successful_runs
            }
            if timed_out_runs > 0:
                result["warning"] = f"{timed_out_runs}/{num_runs} runs timed out (limit: {timeout}s)"
            return result

        except Exception as e:
            logging.error(f"Verilator simulation error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def parse_coverage(self, coverage_db_path: Path) -> CoverageResult:
        """Parse Verilator coverage database (.dat).

        Converts binary .dat file to LCOV .info format, then parses to extract
        file-level coverage and uncovered line numbers.

        Args:
            coverage_db_path: Path to .dat coverage database

        Returns:
            CoverageResult with normalized coverage data

        Raises:
            FileNotFoundError: If coverage database doesn't exist
            RuntimeError: If coverage conversion or parsing fails
        """
        if not coverage_db_path.exists():
            raise FileNotFoundError(f"Coverage database not found: {coverage_db_path}")

        # Verify coverage file is not empty
        if coverage_db_path.stat().st_size == 0:
            raise RuntimeError(f"Coverage database is empty: {coverage_db_path}")

        # Output paths
        info_path = coverage_db_path.with_suffix('.info')
        annotate_dir = coverage_db_path.parent / "annotated"
        annotate_dir.mkdir(parents=True, exist_ok=True)

        # Convert .dat to .info using verilator_coverage
        verilator_coverage_tool = self.simulator_path / "verilator_coverage"
        if not verilator_coverage_tool.exists():
            raise RuntimeError(f"verilator_coverage tool not found: {verilator_coverage_tool}")

        command = [
            str(verilator_coverage_tool),
            "-write-info", str(info_path),
            "--annotate", str(annotate_dir),
            str(coverage_db_path)
        ]

        logging.info(f"Converting Verilator coverage: {coverage_db_path} -> {info_path}")
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(
                f"Coverage conversion failed (return code {result.returncode}):\n"
                f"Command: {' '.join(command)}\n"
                f"Error: {result.stderr}"
            )

        # Verify .info file was created
        if not info_path.exists():
            raise RuntimeError(f"LCOV info file not created: {info_path}")

        # Parse LCOV .info file
        total_coverage, file_breakdown, uncovered_lines = self._parse_lcov_info(info_path)

        return CoverageResult(
            total_coverage=total_coverage,
            breakdown=file_breakdown,
            uncovered_lines=uncovered_lines
        )

    def _parse_lcov_info(self, info_path: Path) -> Tuple[float, Dict[str, float], Dict[str, List[int]]]:
        """Parse LCOV .info file to extract coverage data.

        Uses the lcovparser library (must be installed separately).

        Args:
            info_path: Path to LCOV .info file

        Returns:
            Tuple of (total_coverage, file_breakdown, uncovered_lines)
        """
        try:
            # Import lcovparser (from legacy llm-verif)
            try:
                from llm_verif.lcovparser import parse_file as lcov_parse_file
            except ImportError:
                # Try direct import if llm_verif is not in path
                import sys
                sys.path.insert(0, '/home/vpatel69/capstone/llm-verif')
                from llm_verif.lcovparser import parse_file as lcov_parse_file

            # Parse LCOV report
            report = lcov_parse_file(str(info_path))

            total_lines = 0
            total_hit = 0
            file_breakdown = {}
            uncovered_lines = {}

            # Process each file in the report
            for filename in report:
                rec = report[filename]

                # Skip testbench files from coverage (focus on DUT)
                # Check for common testbench naming patterns: tb_*, *_tb.*, testbench.*
                filename_lower = filename.lower()
                if any(pattern in filename_lower for pattern in ['tb_', '_tb.', 'testbench']):
                    logging.debug(f"Skipping testbench file from coverage: {filename}")
                    continue

                lines_found = len(rec.lines)
                lines_hit = sum(1 for hits in rec.lines.values() if hits > 0)

                if lines_found == 0:
                    continue

                # Calculate per-file coverage
                pct = (lines_hit / lines_found * 100.0)

                total_lines += lines_found
                total_hit += lines_hit
                file_breakdown[filename] = round(pct, 2)

                # Extract uncovered line numbers
                uncovered = sorted([ln for ln, hits in rec.lines.items() if hits == 0])
                if uncovered:
                    uncovered_lines[filename] = uncovered

            # Calculate total coverage
            total_coverage = (total_hit / total_lines * 100.0) if total_lines > 0 else 0.0

            logging.info(f"Verilator coverage: {total_coverage:.2f}% ({total_hit}/{total_lines} lines)")
            logging.info(f"Coverage breakdown: {len(file_breakdown)} design files")

            return round(total_coverage, 2), file_breakdown, uncovered_lines

        except ImportError as e:
            logging.error(f"lcovparser not installed: {e}")
            logging.error("Please install: pip install lcovparser")
            return 0.0, {}, {}
        except Exception as e:
            logging.error(f"Verilator LCOV parsing failed: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return 0.0, {}, {}

    @staticmethod
    def _check_errors(output: str) -> bool:
        """Check if Verilator output contains errors.

        Verilator uses %Error: and %Fatal: prefixes for errors.

        Args:
            output: Verilator stdout/stderr output

        Returns:
            True if errors found, False otherwise
        """
        return bool(re.search(r'%(?:Error|Fatal):', output))

    @staticmethod
    def _extract_error_message(output: str) -> str:
        """Extract concise error message from Verilator output.

        Args:
            output: Verilator stdout/stderr output

        Returns:
            Extracted error message or full output if no specific error found
        """
        # Look for %Error: or %Fatal: lines
        error_lines = []
        for line in output.split('\n'):
            if re.search(r'%(?:Error|Fatal):', line):
                error_lines.append(line.strip())

        if error_lines:
            return '\n'.join(error_lines[:5])  # Return first 5 error lines

        # If no specific errors but compilation failed, return last 10 lines
        lines = output.strip().split('\n')
        return '\n'.join(lines[-10:]) if lines else "Unknown compilation error"

    def merge_cumulative_coverage(self, new_dat: Path, cumulative_dat: Path) -> Path:
        """Merge new iteration coverage with cumulative coverage database.

        If cumulative_dat doesn't exist, the new_dat becomes the cumulative.
        Otherwise, merges both using verilator_coverage tool.

        Args:
            new_dat: Path to new iteration's coverage database (.dat)
            cumulative_dat: Path to cumulative coverage database (.dat)

        Returns:
            Path to the updated cumulative coverage database

        Raises:
            RuntimeError: If merge operation fails
        """
        if not new_dat.exists():
            raise FileNotFoundError(f"New coverage database not found: {new_dat}")

        # If no cumulative exists yet, copy new as cumulative
        if not cumulative_dat.exists():
            import shutil
            shutil.copy(new_dat, cumulative_dat)
            logging.info(f"Initialized cumulative coverage: {cumulative_dat}")
            return cumulative_dat

        # Merge using verilator_coverage tool
        # verilator_coverage can take multiple .dat files and merge them
        verilator_coverage_tool = self.simulator_path / "verilator_coverage"
        if not verilator_coverage_tool.exists():
            raise RuntimeError(f"verilator_coverage tool not found: {verilator_coverage_tool}")

        # Create temp file for merged result
        temp_merged = cumulative_dat.parent / "cumulative_temp.dat"

        command = [
            str(verilator_coverage_tool),
            "--write", str(temp_merged),
            str(cumulative_dat),
            str(new_dat)
        ]

        logging.info(f"Merging iteration coverage into cumulative database")
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Cumulative coverage merge failed: {result.stderr}")

        # Replace cumulative with merged result
        import shutil
        shutil.move(temp_merged, cumulative_dat)
        logging.info(f"Updated cumulative coverage: {cumulative_dat}")

        return cumulative_dat

    @staticmethod
    def cleanup(work_dir: Path) -> None:
        """Clean up Verilator-specific files.

        Removes:
        - obj_dir/ directory (compiled C++ and executables)
        - .vcd waveform dump files

        Args:
            work_dir: Working directory containing Verilator artifacts
        """
        import shutil

        try:
            # Remove obj_dir (compiled files and executables)
            obj_dir = work_dir / "obj_dir"
            if obj_dir.exists():
                shutil.rmtree(obj_dir, ignore_errors=True)
                logging.info(f"Cleaned up Verilator obj_dir: {obj_dir}")

            # Remove .vcd waveform files
            for vcd_file in work_dir.glob("*.vcd"):
                vcd_file.unlink()
                logging.info(f"Cleaned up VCD file: {vcd_file}")

        except Exception as e:
            logging.warning(f"Verilator cleanup error: {e}")
