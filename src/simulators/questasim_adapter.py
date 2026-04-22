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
    build_vlog_commands_no_cover,
    build_vsim_command,
    build_vcover_merge_command,
    check_questasim_success,
    build_uvm_vlib_uvm_command,
    build_uvm_vlog_uvm_command,
    build_uvm_vmap_command,
    build_uvm_vlog_design_command,
    build_uvm_vopt_command,
    build_uvm_vsim_command,
)


class QuestasimAdapter(SimulatorAdapter):
    """QuestaSim simulator adapter.

    Implements the SimulatorAdapter interface for Mentor Graphics QuestaSim.
    Uses vlog for compilation, vsim for simulation, and vcover for coverage
    database merging. Supports both standard and UVM compilation flows.
    """

    def __init__(self, simulator_path: Path):
        super().__init__(simulator_path)
        self._uvm_config = None  # Set via set_uvm_config() when UVM mode active

    def set_uvm_config(self, uvm_config: dict):
        """Set UVM-specific configuration for compile/simulate.

        Args:
            uvm_config: Dict with keys: filelist, top_module, test_name,
                        dpi_lib, uvm_home, testbench_dir, sequence_file
        """
        self._uvm_config = uvm_config
        logging.info(f"QuestaSim UVM config set: top={uvm_config.get('top_module')}")

    # Lines matching these patterns are QuestaSim vlog (compile) boilerplate
    _COMPILE_BOILERPLATE_PATTERNS = [
        re.compile(r"^Questa Intel"),              # version banner
        re.compile(r"^QuestaSim-64 vlog"),         # version banner (alternate form)
        re.compile(r"^Start time:"),               # timestamp
        re.compile(r"^vlog\s"),                    # echoed command with long paths
        re.compile(r"^-- Compiling module\s"),     # per-module compilation status
        re.compile(r"^-- Compiling package\s"),    # per-package compilation status
        re.compile(r"^-- Importing package\s"),    # package import status
        re.compile(r"^Top level modules:"),         # top-level header
        re.compile(r"^\t\w"),                       # indented module name under "Top level modules:"
        re.compile(r"^End time:"),                 # end timestamp
        re.compile(r"^\*\* Note: \(vlog-"),        # informational notes (e.g. vlog-220)
        re.compile(r"^\*\* Warning:.*\/deps\/"),   # warnings from dep files (not actionable)
        re.compile(r"^Errors: 0,"),                # clean summary line (no errors)
        # vlog-13203: "option.cross_auto_bin_max = 0 is non-LRM compliant" — expected/harmless
        # These fire for every covergroup in trng_tb.sv / other fixed tb_llm files.
        # They are not actionable and drown out real errors in the LLM-visible output.
        re.compile(r"^\*\* Warning:.*\(vlog-13203\)"),
        # vopt-10587: "+acc turns off some optimizations" — expected when using +acc for coverage
        re.compile(r"^\*\* Warning: \(vopt-10587\)"),
        # vopt / vlog version banners and timestamps
        re.compile(r"^QuestaSim-64 vopt"),
        re.compile(r"^QuestaSim-64 vmap"),
        re.compile(r"^vopt\s"),
        re.compile(r"^vmap\s"),
        re.compile(r"^Analyzing design"),
        re.compile(r"^\*\* Note: \(vopt-"),        # informational vopt notes
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

    @staticmethod
    def _shorten_paths(output: str) -> str:
        """Collapse long absolute paths to short relative forms."""
        # /home/.../data/<design>/<subdir>/file.sv -> <design>/<subdir>/file.sv
        output = re.sub(r'/\S+/data/([^/]+/)', r'\1', output)
        # /home/.../work/.../testbenches/file.sv -> testbenches/file.sv
        output = re.sub(r'/\S+/testbenches/', r'testbenches/', output)
        return output

    @staticmethod
    def _extract_errors_with_context(lines: list, context: int = 2) -> str:
        """Extract only error/warning lines with surrounding context.

        Used when filtered output is still too large for the LLM.
        """
        error_indices = set()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("** Error") or stripped.startswith("** Warning"):
                for j in range(max(0, i - context), min(len(lines), i + context + 1)):
                    error_indices.add(j)
            # Always include the final summary line
            if re.match(r"^Errors: \d+,", stripped):
                error_indices.add(i)

        if not error_indices:
            return "\n".join(lines)

        sorted_indices = sorted(error_indices)
        result = []
        prev_idx = -2
        for idx in sorted_indices:
            if idx > prev_idx + 1:
                skipped = idx - prev_idx - 1
                if prev_idx >= 0 and skipped > 0:
                    result.append(f"... ({skipped} lines omitted) ...")
            result.append(lines[idx])
            prev_idx = idx

        # Note trailing omitted lines
        remaining = len(lines) - 1 - prev_idx
        if remaining > 0:
            result.append(f"... ({remaining} lines omitted) ...")

        return "\n".join(result)

    def filter_compile_output(self, output: str) -> str:
        """Strip QuestaSim vlog boilerplate from compiler output.

        Removes the version banner, echoed command (with long absolute paths),
        per-module/package compilation status, import lines, timestamps,
        informational notes, and warnings from dependency files.  Keeps
        ``** Error``, ``** Warning`` (from design/testbench files), and the
        final ``Errors: N, Warnings: N`` summary.

        If the output is still large after pattern filtering (>50 lines),
        switches to extracting only error/warning lines with context.
        """
        filtered = self._filter_by_patterns(output, self._COMPILE_BOILERPLATE_PATTERNS)

        # If still large, extract only errors + context
        lines = filtered.splitlines()
        if len(lines) > 50:
            filtered = self._extract_errors_with_context(lines)

        # Shorten absolute paths to reduce token waste
        filtered = self._shorten_paths(filtered)

        return filtered

    def filter_sim_output(self, output: str) -> str:
        """Strip QuestaSim vsim boilerplate from simulator output.

        Removes copyright banners, loading messages, coverage commands, and
        informational notes that waste LLM input tokens.  Keeps errors,
        warnings, $finish, timing, seed, and run headers.
        """
        filtered = self._filter_by_patterns(output, self._BOILERPLATE_PATTERNS)
        return self._shorten_paths(filtered)

    def compile(self, testbench_path: Path, design_files: List[Path],
                work_dir: Path, timeout: int,
                compile_deps_files: List[Path] = None,
                functional_coverage: bool = False) -> Dict[str, Any]:
        """Compile testbench using QuestaSim's vlog compiler.

        Args:
            testbench_path: Path to testbench SystemVerilog file
            design_files: List of design RTL files
            work_dir: Working directory (must contain 'work' library)
            timeout: Compilation timeout in seconds
            compile_deps_files: Optional dependency files compiled without
                coverage instrumentation

        Returns:
            Compilation result dictionary with success status and outputs
        """
        if self._uvm_config:
            return self._compile_uvm(work_dir, timeout)

        try:
            all_stdout = []
            all_stderr = []
            last_returncode = 0

            # Pass 1: Compile dependency files WITHOUT coverage instrumentation
            compile_deps_files = compile_deps_files or []
            if compile_deps_files:
                deps_commands = build_vlog_commands_no_cover(
                    self.simulator_path, compile_deps_files
                )
                for command in deps_commands:
                    # logging.info(f"QuestaSim compile deps (no coverage): {' '.join(str(c) for c in command)}")
                    logging.info(f"QuestaSim: compiling dependencies")

                    result = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        cwd=str(work_dir)
                    )

                    all_stdout.append(result.stdout)
                    all_stderr.append(result.stderr)
                    last_returncode = result.returncode

                    if not check_questasim_success(result.stdout):
                        return {
                            "success": False,
                            "return_code": result.returncode,
                            "stdout": "\n".join(all_stdout),
                            "stderr": "\n".join(all_stderr),
                            "log_path": ""
                        }

            # Pass 2: Compile design files + testbench WITH coverage
            # Build separate vlog commands for .v (Verilog) and .sv (SystemVerilog)
            # files.  Legacy .v files may use identifiers like ``return`` that
            # clash with SystemVerilog reserved keywords.
            pass2_stdout = []
            pass2_stderr = []
            commands = build_vlog_commands(self.simulator_path, testbench_path, design_files,
                                          incdir_files=compile_deps_files,
                                          functional_coverage=functional_coverage)

            for command in commands:
                # logging.info(f"QuestaSim compile: {' '.join(str(c) for c in command)}")
                logging.info(f"QuestaSim: compiling design files")

                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(work_dir)  # Run in work directory for work library
                )

                all_stdout.append(result.stdout)
                all_stderr.append(result.stderr)
                pass2_stdout.append(result.stdout)
                pass2_stderr.append(result.stderr)
                last_returncode = result.returncode

                # Fail fast: if this pass has errors, stop immediately
                if not check_questasim_success(result.stdout):
                    return {
                        "success": False,
                        "return_code": result.returncode,
                        # LLM sees only Pass 2 output (the actionable part)
                        "stdout": "\n".join(pass2_stdout),
                        "stderr": "\n".join(pass2_stderr),
                        # Full output preserved for disk logging
                        "full_stdout": "\n".join(all_stdout),
                        "full_stderr": "\n".join(all_stderr),
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

    def _compile_uvm(self, work_dir: Path, timeout: int) -> Dict[str, Any]:
        """UVM 3-step compilation flow: vlib → vlog → vopt.

        Uses the .f file from uvm_config (already prepared with absolute paths
        and pointing to the LLM-generated sequence/test files in the work dir).
        Steps:
          1. vlib work + vlib uvm_lib  (clean slate each compile)
          2. vlog UVM 1.2 from source into uvm_lib
          3. vmap mtiUvm → uvm_lib  (prevents dual-UVM conflict)
          4. vlog design + testbench with -mfcu -L uvm_lib
          5. vopt with +cover=bcestf
        """
        cfg = self._uvm_config
        filelist = Path(cfg["filelist"])
        top_module = cfg["top_module"]
        all_stdout = []
        all_stderr = []

        try:
            import shutil
            for lib_name in ("work", "uvm_lib"):
                lib_path = work_dir / lib_name
                if lib_path.exists():
                    shutil.rmtree(lib_path)
                    logging.info(f"Removed stale QuestaSim {lib_name} library")
            local_ini = work_dir / "modelsim.ini"
            if local_ini.exists():
                local_ini.unlink()

            # Step 1a: vlib work
            vlib_cmd = [str(self.simulator_path / "vlib"), "work"]
            logging.info("UVM vlib: creating work library")
            result = subprocess.run(vlib_cmd, capture_output=True, text=True,
                                    timeout=timeout, cwd=str(work_dir))
            all_stdout.append(f"=== vlib (work) ===\n{result.stdout}")
            all_stderr.append(result.stderr)
            if result.returncode != 0:
                return {"success": False, "return_code": result.returncode,
                        "stdout": "\n".join(all_stdout), "stderr": "\n".join(all_stderr),
                        "error": f"vlib work failed: {result.stderr}", "log_path": ""}

            # Step 1b: vlib uvm_lib
            vlib_uvm_cmd = build_uvm_vlib_uvm_command(self.simulator_path)
            logging.info("UVM vlib: creating uvm_lib library")
            result = subprocess.run(vlib_uvm_cmd, capture_output=True, text=True,
                                    timeout=timeout, cwd=str(work_dir))
            all_stdout.append(f"=== vlib (uvm_lib) ===\n{result.stdout}")
            all_stderr.append(result.stderr)
            if result.returncode != 0:
                return {"success": False, "return_code": result.returncode,
                        "stdout": "\n".join(all_stdout), "stderr": "\n".join(all_stderr),
                        "error": f"vlib uvm_lib failed: {result.stderr}", "log_path": ""}

            # Step 2: vlog UVM 1.2 from source
            uvm_home = cfg.get("uvm_home", "/opt/siemens/questasim/uvm-1.2")
            vlog_uvm_cmd = build_uvm_vlog_uvm_command(self.simulator_path, uvm_home)
            logging.info("UVM vlog: compiling UVM 1.2 from source")
            result = subprocess.run(vlog_uvm_cmd, capture_output=True, text=True,
                                    timeout=timeout, cwd=str(work_dir))
            all_stdout.append(f"=== vlog (uvm_pkg) ===\n{result.stdout}")
            all_stderr.append(result.stderr)
            if result.returncode != 0:
                return {"success": False, "return_code": result.returncode,
                        "stdout": "\n".join(all_stdout), "stderr": "\n".join(all_stderr),
                        "error": "vlog UVM compilation failed", "log_path": ""}

            # Step 3: vmap mtiUvm → uvm_lib (critical: prevents dual-UVM conflict)
            vmap_cmd = build_uvm_vmap_command(self.simulator_path)
            logging.info("UVM vmap: redirecting mtiUvm → uvm_lib")
            result = subprocess.run(vmap_cmd, capture_output=True, text=True,
                                    timeout=timeout, cwd=str(work_dir))
            all_stdout.append(f"=== vmap (mtiUvm → uvm_lib) ===\n{result.stdout}")
            all_stderr.append(result.stderr)
            if result.returncode != 0:
                return {"success": False, "return_code": result.returncode,
                        "stdout": "\n".join(all_stdout), "stderr": "\n".join(all_stderr),
                        "error": f"vmap mtiUvm failed: {result.stderr}", "log_path": ""}

            # Step 4: vlog design + testbench with -mfcu
            vlog_cmd = build_uvm_vlog_design_command(self.simulator_path, filelist, uvm_home)
            logging.info("UVM vlog: compiling design + testbench")
            result = subprocess.run(vlog_cmd, capture_output=True, text=True,
                                    timeout=timeout, cwd=str(work_dir))
            all_stdout.append(f"=== vlog (design) ===\n{result.stdout}")
            all_stderr.append(result.stderr)
            if not check_questasim_success(result.stdout):
                return {"success": False, "return_code": result.returncode,
                        "stdout": "\n".join(all_stdout), "stderr": "\n".join(all_stderr),
                        "error": "vlog design compilation failed", "log_path": ""}

            # Step 5: vopt with coverage instrumentation
            vopt_cmd = build_uvm_vopt_command(self.simulator_path, top_module)
            logging.info("UVM vopt: optimizing with coverage")
            result = subprocess.run(vopt_cmd, capture_output=True, text=True,
                                    timeout=timeout, cwd=str(work_dir))
            all_stdout.append(f"=== vopt ===\n{result.stdout}")
            all_stderr.append(result.stderr)
            if result.returncode != 0:
                return {"success": False, "return_code": result.returncode,
                        "stdout": "\n".join(all_stdout), "stderr": "\n".join(all_stderr),
                        "error": "vopt optimization failed", "log_path": ""}

            return {"success": True, "return_code": 0,
                    "stdout": "\n".join(all_stdout), "stderr": "\n".join(all_stderr),
                    "log_path": ""}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"UVM compilation timeout after {timeout}s"}
        except Exception as e:
            logging.error(f"UVM compilation error: {e}")
            return {"success": False, "error": str(e)}

    def simulate(self, testbench_name: str, num_runs: int,
                 work_dir: Path, iteration: int, timeout: int) -> Dict[str, Any]:
        """Run QuestaSim simulation with coverage collection.

        Dispatches to UVM flow if UVM config is set, otherwise standard flow.

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
        if self._uvm_config:
            return self._simulate_uvm(num_runs, work_dir, iteration, timeout)

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

    def _simulate_uvm(self, num_runs: int, work_dir: Path,
                      iteration: int, timeout: int) -> Dict[str, Any]:
        """UVM simulation using optimized design (opt_top) with UVM flags.

        Runs multiple seeds and merges coverage, same as standard flow but
        with UVM-specific vsim command (DPI lib, +UVM_TESTNAME, etc.).
        """
        cfg = self._uvm_config
        test_name = cfg["test_name"]
        dpi_lib = cfg["dpi_lib"]

        try:
            coverage_dir = work_dir / "coverage"
            coverage_dir.mkdir(parents=True, exist_ok=True)

            ucdb_files = []
            all_stdout = []
            all_stderr = []

            for run_idx in range(num_runs):
                ucdb_filename = f"iter_{iteration}_run_{run_idx}.ucdb"
                ucdb_abs_path = coverage_dir / ucdb_filename
                ucdb_rel_path = Path("coverage") / ucdb_filename

                command = build_uvm_vsim_command(
                    self.simulator_path, ucdb_rel_path,
                    test_name=test_name, dpi_lib=dpi_lib,
                )
                logging.info(f"UVM simulation run {run_idx+1}/{num_runs}")

                try:
                    result = subprocess.run(
                        command, capture_output=True, text=True,
                        timeout=timeout, cwd=str(work_dir)
                    )
                    all_stdout.append(f"=== Run {run_idx} ===\n{result.stdout}")
                    all_stderr.append(result.stderr)

                    # UVM_FATAL in output (not just return code) means test died
                    # Match actual fatal messages but NOT the summary "UVM_FATAL :    0"
                    has_uvm_fatal = bool(re.search(r"UVM_FATAL\s+[^:]", result.stdout))
                    if has_uvm_fatal:
                        logging.warning(f"UVM run {run_idx}: UVM_FATAL detected")
                    elif ucdb_abs_path.exists():
                        ucdb_files.append(ucdb_abs_path)
                    else:
                        logging.warning(f"UVM run {run_idx} failed or no UCDB produced")
                except subprocess.TimeoutExpired:
                    logging.warning(f"UVM run {run_idx} timed out")
                    continue

            if not ucdb_files:
                return {
                    "success": False,
                    "error": "All UVM simulation runs failed",
                    "stdout": "\n\n".join(all_stdout),
                    "stderr": "\n".join(all_stderr),
                }

            if len(ucdb_files) > 1:
                merged_ucdb = coverage_dir / f"iter_{iteration}.ucdb"
                merge_command = build_vcover_merge_command(
                    self.simulator_path, merged_ucdb, ucdb_files
                )
                logging.info(f"Merging {len(ucdb_files)} UVM coverage databases")
                result = subprocess.run(merge_command, capture_output=True, text=True)
                if result.returncode != 0:
                    return {"success": False, "error": f"Coverage merge failed: {result.stderr}"}
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
            logging.error(f"UVM simulation error: {e}")
            return {"success": False, "error": str(e)}

    def parse_coverage(self, coverage_db_path: Path,
                       design_files: List[Path] = None) -> CoverageResult:
        """Parse QuestaSim coverage database (.ucdb).

        Generates XML report from .ucdb file and parses it to extract
        module-level coverage and uncovered line numbers.

        Args:
            coverage_db_path: Path to .ucdb coverage database
            design_files: Optional list of RTL design file paths. When
                provided, only design units whose source files overlap with
                this list are counted, filtering out UVM testbench
                infrastructure that would otherwise dilute RTL coverage.

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
        total_coverage, module_breakdown, uncovered_lines = self._parse_coverage_xml(
            xml_path, design_files=design_files
        )

        return CoverageResult(
            total_coverage=total_coverage,
            breakdown=module_breakdown,
            uncovered_lines=uncovered_lines
        )

    def _parse_coverage_xml(self, xml_path: Path,
                            design_files: List[Path] = None,
                            ) -> Tuple[float, Dict[str, float], Dict[str, List[int]]]:
        """Parse QuestaSim XML coverage report.

        Args:
            xml_path: Path to XML coverage report
            design_files: Optional list of resolved RTL file paths. When
                provided, a DU is included only if at least one of its
                source files matches a design file. Matches on both resolved
                path and filename to handle UVM copies of RTL into
                verif/UVM/rtl/ directories.

        Returns:
            Tuple of (total_coverage, module_breakdown, uncovered_lines)
        """
        if design_files:
            design_file_set = {str(Path(f).resolve()) for f in design_files}
            design_file_names = {Path(f).name for f in design_files}
        else:
            design_file_set = None
            design_file_names = None

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

                # Collect all source file paths for this DU
                du_file_paths = []
                for fm in du_data.findall('.//fileMap'):
                    p = fm.get('path')
                    if p:
                        du_file_paths.append(str(Path(p).resolve()))

                # Filter: only include DUs whose source files are design files
                if design_file_set is not None:
                    match = any(
                        p in design_file_set or Path(p).name in design_file_names
                        for p in du_file_paths
                    )
                    if not match:
                        logging.debug(f"Skipping DU '{du_name}' — not in design files")
                        continue
                else:
                    # Legacy fallback: skip known testbench DU name
                    if du_name == 'tb_llm':
                        continue

                # Get primary file path (first fileMap) for uncovered_lines key
                file_path = du_file_paths[0] if du_file_paths else "unknown"

                # Get statement coverage stats
                statements = du_data.find('statements')
                if statements is not None:
                    active = int(statements.get('active', 0))
                    hits = int(statements.get('hits', 0))
                    percent = float(statements.get('percent', 0.0))

                    total_active += active
                    total_hits += hits
                    module_breakdown[Path(file_path).name] = percent

                    # Extract uncovered line numbers. Use a set to deduplicate
                    uncovered = set()
                    for stmt in du_data.findall('.//stmt'):
                        if stmt.get('hits') == '0':
                            uncovered.add(int(stmt.get('ln')))

                    if uncovered:
                        uncovered_lines[file_path] = sorted(uncovered)

            # Calculate total coverage
            total_coverage = (total_hits / total_active * 100.0) if total_active > 0 else 0.0

            return round(total_coverage, 2), module_breakdown, uncovered_lines

        except (ET.ParseError, FileNotFoundError) as e:
            logging.error(f"QuestaSim coverage XML parsing failed: {e}")
            return 0.0, {}, {}

    def parse_functional_coverage(self, coverage_db_path: Path) -> Dict:
        """Parse functional (covergroup) coverage from a QuestaSim UCDB.

        Generates a text report using vcover and parses it with the state
        machine parser to extract covergroup/coverpoint/bin-level data.

        Args:
            coverage_db_path: Path to .ucdb coverage database

        Returns:
            Dict with 'total_coverage' and 'covergroups' list (see
            parse_functional_coverage_text for full schema).
        """
        from ..utils.questasim import (
            build_functional_coverage_report_command,
            parse_functional_coverage_text,
        )

        report_path = coverage_db_path.parent / f"{coverage_db_path.stem}_funcov_report.txt"
        command = build_functional_coverage_report_command(
            self.simulator_path, coverage_db_path, report_path
        )

        logging.info("Generating QuestaSim functional coverage report")
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            logging.warning(f"vcover report returned non-zero ({result.returncode}): {result.stderr[:200]}")

        return parse_functional_coverage_text(report_path)

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
