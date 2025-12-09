import os
import logging
import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Iterable
import fnmatch

from llm_verif.simulator import ArtifactPlan, Simulator, CoverageResponse, DU
from llm_verif.lcovparser import Report, Record
from llm_verif.lcovparser import parse_file as lcov_parse_file

# ============================================================================
# Verilator-specific data structures and utilities
# ============================================================================

@dataclass
class FileCoverage:
    """Represents line coverage data for a single file (Verilator-specific)."""
    path: str
    total_lines: int
    covered_lines: int
    coverage_pct: float
    uncovered_lines: List[int]

class Verilator(Simulator):
  def __init__(self, simulator_path: str, design_unit: str):
    super().__init__(simulator_path, design_unit)

  # ============================================================================
  # Utility methods (private)
  # ============================================================================

  @staticmethod
  def _norm(p: str) -> str:
    """Normalize path for cross-platform compatibility."""
    return os.path.normpath(p).replace("\\", "/")

  @staticmethod
  def _should_exclude(path: str, patterns: Iterable[str]) -> bool:
    """
    Return True if 'path' matches any pattern in 'patterns'.
    Patterns are tested against both the normalized full path and the basename.
    Supports shell-style globs: *, **, ?
    """
    if not patterns:
      return False
    npath = Verilator._norm(path)
    base = os.path.basename(npath)
    for pat in patterns:
      if fnmatch.fnmatch(npath, pat) or fnmatch.fnmatch(base, pat):
        return True
    return False

  @staticmethod
  def _load_file_coverage(
      info_path: str,
      exclude: Iterable[str] = (),
      ignore_incorrect_counts: bool = True,
      merge_duplicate_line_hit_counts: bool = True,
  ) -> List[FileCoverage]:
    """
    Parse LCOV .info and return by-file coverage (excluding any file that matches 'exclude').
    """
    if lcov_parse_file is None:
      raise ImportError("lcovparser not installed. Install with: pip install lcovparser")

    report: Report = lcov_parse_file(
        info_path,
        ignore_incorrect_counts=ignore_incorrect_counts,
        merge_duplicate_line_hit_counts=merge_duplicate_line_hit_counts,
    )

    rows: List[FileCoverage] = []
    for filename in report:
      rec: Record = report[filename]
      if Verilator._should_exclude(rec.filename, exclude):
        continue

      lines_found = len(rec.lines)
      lines_hit = sum(1 for hits in rec.lines.values() if hits > 0)
      pct = (lines_hit / lines_found * 100.0) if lines_found else 0.0
      uncovered = sorted(ln for ln, hits in rec.lines.items() if hits == 0)

      rows.append(FileCoverage(
          path=Verilator._norm(rec.filename),
          total_lines=lines_found,
          covered_lines=lines_hit,
          coverage_pct=round(pct, 2),
          uncovered_lines=uncovered,
      ))

    # Sort: lowest coverage first, then larger files first, then filename
    rows.sort(key=lambda r: (r.coverage_pct, -r.total_lines, r.path))
    return rows

  @staticmethod
  def _total_coverage(rows: List[FileCoverage]) -> Tuple[int, int, float]:
    """
    Aggregate total coverage across all provided files.
    Returns (total_lines_found, total_lines_hit, coverage_pct).
    """
    lf = sum(r.total_lines for r in rows)
    lh = sum(r.covered_lines for r in rows)
    pct = (lh / lf * 100.0) if lf else 0.0
    return lf, lh, round(pct, 2)

  # ============================================================================
  # Public methods
  # ============================================================================

  @staticmethod
  def cleanup(directory: str):
    """
    Cleanup temporary Verilator simulation files.

    Args:
        directory (str): Directory containing temporary files.
    """
    import shutil
    try:
      # Remove Verilator generated directories
      shutil.rmtree(os.path.join(directory, "obj_dir"), ignore_errors=True)
      # Remove any .vcd files (waveform dumps)
      for file in os.listdir(directory):
        if file.endswith('.vcd'):
          os.remove(os.path.join(directory, file))
    except FileNotFoundError:
      pass
    except Exception as e:
      logging.warning(f"Error during Verilator cleanup: {e}")

  def plan_artifacts(self, work_dir: str | Path, tb_stem: str, sim_runs: int) -> ArtifactPlan:
    wd = str(work_dir)
    tb_path = os.path.join(wd, f"{tb_stem}.sv")
    compile_log = os.path.join(wd, f"{tb_stem}_compile.log")
    sim_logs = [os.path.join(wd, f"{tb_stem}_{i}_sim.log") for i in range(sim_runs)]
    per_run_coverage_dbs = [os.path.join(wd, f"{tb_stem}_{i}_coverage.dat") for i in range(sim_runs)]
    merged_coverage_db = os.path.join(wd, f"{tb_stem}_coverage.dat")
    info_path = os.path.join(wd, f"{tb_stem}_coverage.info")
    report_path = info_path
    annotate_dir = os.path.join(wd, f"{tb_stem}_annotated")
    return ArtifactPlan(
      work_dir=wd,
      tb_path=tb_path,
      compile_log=compile_log,
      sim_logs=sim_logs,
      per_run_coverage_dbs=per_run_coverage_dbs,
      merged_coverage_db=merged_coverage_db,
      report_path=report_path,
      annotate_dir=annotate_dir,
      info_path=info_path
    )


  def build_compile_command(self, work_dir: str,testbench_path: str, data_point: dict) -> str:
    return f"{self.simulator_path}/verilator --binary -j 4 --coverage-line -Wno-fatal --Mdir {work_dir}/obj_dir {testbench_path} {' '.join(data_point['design'])} {' '.join(data_point['design_context'])}"

  """
  COMPILE AND SIMULATE
  """

  def compile(self, work_dir: str, testbench_path: str, data_point: dict[str, str | list[str]]) -> str:
    """
    Compile the design and testbench using Verilator.

    Args:
        testbench_path (str): Path to the testbench file.
        data_point (dict): Dictionary containing design and context files.
      
    Returns:
        str: Compilation output or error message.
    """

    compile_command = self.build_compile_command(work_dir, testbench_path, data_point).split()
    return self.run_command(compile_command)

  def simulate(self, work_dir: str, testbench_module: str, coverage_dat_path: str) -> str:
    """
    Simulate the compiled design using Verilator.

    Note: Coverage output file is set at compile time via +verilator+coverage+file+
    and cannot be changed per simulation run.

    Args:
        testbench_module (str): Name of the testbench module.

    Returns:
        str: Simulation output or error message.
    """

    command = [
      f"{work_dir}/obj_dir/V{testbench_module}",
      f"+verilator+coverage+file+{coverage_dat_path}" 
    ]

    return self.run_command(command, timeout=300)
  
  def run_simulation_flow(self, work_dir: str | Path, tb_name: str, data_point: dict[str, str | list[str]] | None, sim_runs: int = 1) -> CoverageResponse:
    """
    Run the complete Verilator simulation flow: compile, simulate, generate coverage.

    Args:
        work_dir: Working directory for artifacts
        tb_name: Testbench filename (e.g., "tb_llm_design_0_0_0.sv")
        data_point: Dictionary containing design and context files
        sim_runs: Number of simulation runs to perform

    Returns:
        CoverageResponse with coverage results or error information
    """
    # Extract testbench stem from filename (remove extension)
    tb_stem = os.path.splitext(tb_name)[0]

    # Use ArtifactPlan for systematic file path management
    artifact_plan = self.plan_artifacts(work_dir, tb_stem, sim_runs)

    # Extract paths from artifact plan
    tb_path = artifact_plan.tb_path
    compile_log_path = artifact_plan.compile_log
    coverage_info_path = artifact_plan.info_path
    coverage_annotate_dir_path = artifact_plan.annotate_dir

    design_dir = os.path.split(os.path.split(tb_path)[0])[0]
    tb_module_name = self.get_testbench_name(tb_path)

    if not self.has_finish(tb_path):
      logging.error(f"Testbench {tb_path} does not contain 'finish' statement.")
      return CoverageResponse(False, 5, "No $finish found in testbench", [], 0)
    
    self.cleanup(design_dir)

    # Compilation phase
    try:
      # For Verilator, coverage output file is set at compile time via +verilator+coverage+file+
      # All simulation runs will write to this single .dat file
      compile_output = self.compile(work_dir, tb_path, data_point) # type: ignore
      with open(compile_log_path, 'w') as f:
        f.write(compile_output)

      if Verilator.check_errors(compile_output):
        logging.error(f"Compilation error for {tb_path}. Check {compile_log_path} for details.")
        return CoverageResponse(False, 1, compile_output, [], 0)

    except RuntimeError as e:
      logging.error(f"Compilation failed for {tb_path}: {e}")
      return CoverageResponse(False, 1, str(e), [], 0)

    # Simulation phase - run multiple simulations
    # Note: All runs accumulate coverage into the single .dat file set at compile time
    try:
      for i in range(sim_runs):
        sim_log_path_i = artifact_plan.sim_logs[i]

        sim_output = self.simulate(str(work_dir), tb_stem, artifact_plan.merged_coverage_db)
        with open(sim_log_path_i, 'w') as f:
          f.write(sim_output)

        if Verilator.check_errors(sim_output):
          logging.error(f"Simulation error for {tb_path}. Check {sim_log_path_i} for details.")
          raise RuntimeError(sim_output)

        logging.info(f"Simulation run {i+1}/{sim_runs} completed for {tb_path}.")

    except RuntimeError as e:
      logging.error(f"Simulation failed for {tb_path}: {e}")
      return CoverageResponse(False, 2, str(e), [], 0)

    # Coverage generation phase - convert the single .dat file to .info format
    try:
      # Check if coverage database file was created
      if not os.path.exists(artifact_plan.merged_coverage_db):
        error_msg = f"Coverage database not found: {artifact_plan.merged_coverage_db}"
        logging.error(error_msg)
        return CoverageResponse(False, 3, error_msg, [], 0)

      # Since all sim runs wrote to the same .dat file, we just need to convert it to .info
      self.annotate_coverage(
          artifact_plan.merged_coverage_db,
          str(coverage_info_path),
          str(coverage_annotate_dir_path)
      )

      # Check if .info file was created
      if not os.path.exists(str(coverage_info_path)):
        error_msg = f"Coverage .info file not created: {coverage_info_path}"
        logging.error(error_msg)
        return CoverageResponse(False, 3, error_msg, [], 0)

      coverage_list, total_coverage = self.parse_coverage_report(str(coverage_info_path), tb_path)
      logging.info(f"Coverage report generated for {tb_path}: {total_coverage}%")
      return CoverageResponse(True, 0, sim_output, coverage_list, total_coverage)
    except RuntimeError as e:
      logging.error(f"Coverage report generation failed for {tb_path}: {e}")
      return CoverageResponse(False, 3, str(e), [], 0)

    
  """
  GENERATING REPORTS
  """

  def annotate_coverage(self, dat_path: str, info_path: str, annotate_dir_path: str) -> str:
    """
    Annotate coverage data using Verilator's coverage tools.

    Args:
        dat_path (str): Path to the .dat file generated during simulation.
        report_path (str): Path to save the coverage report.

    Returns:
        str: Coverage annotation output or error message.
    """

    command = [
      f"{self.simulator_path}/verilator_coverage",
      "-write-info",
      info_path,
      "--annotate",
      annotate_dir_path,
      dat_path
    ]

    return self.run_command(command)
    
  def generate_merged_coverage_report(self, du: str, coverage_dats: list[str], coverage_dat_path: str, info_path: str, annotated_dir_path: str):
      """
      Generate a merged coverage report from multiple .dat files.

      Args:
          du (str): Design unit name.
          coverage_dats (list[str]): List of .dat file paths to merge.
          coverage_dat_path (str): Path to save the merged .dat file.
          info_path (str): Path to save the .info file (lcov format).
          annotated_dir_path (str): Directory to save annotated source files.

      Raises:
          FileNotFoundError: If any coverage .dat files don't exist
      """
      # Check that all input coverage files exist
      missing_files = [f for f in coverage_dats if not os.path.exists(f)]
      if missing_files:
        raise FileNotFoundError(f"Coverage database files not found: {missing_files}")

      merge_command = [
        f"{self.simulator_path}/verilator_coverage",
        "--write",
        coverage_dat_path,
        "--write-info",
        info_path,
        "--annotate",
        annotated_dir_path,
      ] + coverage_dats

      return self.run_command(merge_command)

  @staticmethod
  def parse_coverage_report(report_path: str, tb_path: str):
    """
    Parse Verilator coverage report from .info file.

    Args:
        report_path: Path to the .info file (LCOV format)
        tb_path: Path to testbench file to exclude from coverage

    Returns:
        Tuple of (file_coverage_list, coverage_percentage)

    Raises:
        FileNotFoundError: If report_path doesn't exist
    """
    if not os.path.exists(report_path):
      raise FileNotFoundError(f"Coverage report not found: {report_path}")

    file_coverage: list[FileCoverage] = Verilator._load_file_coverage(report_path, exclude=[tb_path])
    total_lines, covered_lines, coverage_pct = Verilator._total_coverage(file_coverage)

    return file_coverage, coverage_pct

  @staticmethod
  def check_errors(output: str) -> bool:
    """
    Return True if Verilator output indicates an error or fatal condition.
    Accepts stdout/stderr text from compilation or simulation.
    """
    return bool(re.search(r'\b%(?:Error|Fatal):', output))

  def get_coverage_file_extension(self) -> str:
    """Get the file extension for Verilator coverage database files."""
    return ".dat"
  
  def merge_and_parse_run_coverage(
      self, design_name: str, work_dir: str, run_idx: int, max_iterations: int,
      batch_size: int, sim_runs: int, design_dir: str, use_store: bool
  ) -> CoverageResponse:
    """
    Merge Verilator coverage for a single run and parse the result.

    This method uses ArtifactPlan to systematically find all coverage database files
    for the specified run, then merges and parses them.

    Args:
        design_name: Name of the design module
        work_dir: Working directory containing coverage files
        run_idx: Index of the run to merge
        max_iterations: Maximum iterations per run
        batch_size: Batch size per iteration
        sim_runs: Number of simulation runs per testbench
        design_dir: Design directory path (not used, kept for signature compatibility)
        use_store: Whether using file store
    """
    try:
      # Collect all coverage database files using ArtifactPlan
      coverage_dats = []
      for iter_idx in range(max_iterations):
        for batch_idx in range(batch_size):
          tb_stem = f"tb_llm_{design_name}_{run_idx}_{iter_idx}_{batch_idx}"
          artifact_plan = self.plan_artifacts(work_dir, tb_stem, sim_runs)

          # Only collect the merged_coverage_db (single .dat file per testbench)
          if os.path.exists(artifact_plan.merged_coverage_db):
            coverage_dats.append(artifact_plan.merged_coverage_db)

      if not coverage_dats:
        logging.warning("No .dat files found for merging coverage.")
        return CoverageResponse(False, -1, "No coverage files found")

      # Define output paths for merged coverage
      log_name = f"{work_dir}/merged_coverage_{design_name}"
      merged_dat_path = f"{log_name}.dat"
      merged_info_path = f"{log_name}.info"
      merged_annotate_dir = f"{log_name}_annotated"

      # Merge coverage
      merge_output = self.generate_merged_coverage_report(
        self.design_unit,
        coverage_dats,
        merged_dat_path,
        merged_info_path,
        merged_annotate_dir
      )

      logging.info(f"Merged {len(coverage_dats)} coverage files successfully.")

      # Parse merged coverage - Verilator needs tb_path for exclusion, use empty string for cross-run merge
      merged_coverage, total_coverage = Verilator.parse_coverage_report(merged_info_path, "")
      return CoverageResponse(True, 0, "Merged successfully", merged_coverage, total_coverage)

    except Exception as e:
      logging.error(f"Failed to generate merged coverage: {e}")
      return CoverageResponse(False, -1, f"Merge failed: {e}")

  def merge_and_parse_cross_run_coverage(
      self, design_name: str, work_dir: str, runs: int, max_iterations: int,
      batch_size: int, sim_runs: int, design_dir: str, use_store: bool
  ) -> CoverageResponse:
    """
    Merge Verilator coverage across all runs and parse the result.

    This method uses ArtifactPlan to systematically find all coverage database files,
    then merges and parses them.

    Args:
        design_name: Name of the design module
        work_dir: Working directory containing coverage files
        runs: Number of runs
        max_iterations: Maximum iterations per run
        batch_size: Batch size per iteration
        sim_runs: Number of simulation runs per testbench
        design_dir: Design directory path (not used, kept for signature compatibility)
        use_store: Whether using file store

    Returns:
        CoverageResponse: Response containing merged coverage data
    """
    try:
      # Collect all coverage database files using ArtifactPlan
      coverage_dats = []
      for run_idx in range(runs):
        for iter_idx in range(max_iterations):
          for batch_idx in range(batch_size):
            tb_stem = f"tb_llm_{design_name}_{run_idx}_{iter_idx}_{batch_idx}"
            artifact_plan = self.plan_artifacts(work_dir, tb_stem, sim_runs)

            # Only collect the merged_coverage_db (single .dat file per testbench)
            if os.path.exists(artifact_plan.merged_coverage_db):
              coverage_dats.append(artifact_plan.merged_coverage_db)

      if not coverage_dats:
        logging.warning("No .dat files found for merging coverage.")
        return CoverageResponse(False, -1, "No coverage files found")

      # Define output paths for merged coverage
      log_name = f"{work_dir}/merged_coverage_{design_name}"
      merged_dat_path = f"{log_name}.dat"
      merged_info_path = f"{log_name}.info"
      merged_annotate_dir = f"{log_name}_annotated"

      # Merge coverage
      merge_output = self.generate_merged_coverage_report(
        self.design_unit,
        coverage_dats,
        merged_dat_path,
        merged_info_path,
        merged_annotate_dir
      )

      logging.info(f"Merged {len(coverage_dats)} coverage files successfully.")

      # Parse merged coverage - Verilator needs tb_path for exclusion, use empty string for cross-run merge
      merged_coverage, total_coverage = Verilator.parse_coverage_report(merged_info_path, "")
      return CoverageResponse(True, 0, "Merged successfully", merged_coverage, total_coverage)

    except Exception as e:
      logging.error(f"Failed to generate merged coverage: {e}")
      return CoverageResponse(False, -1, f"Merge failed: {e}")

  def format_coverage_summary(self, coverage: CoverageResponse) -> str:
    """
    Format Verilator coverage summary for LLM consumption.

    Args:
        coverage: Coverage response containing FileCoverage objects

    Returns:
        Formatted string with per-file coverage statistics
    """
    summary = f"Total Design Coverage: {coverage.total_coverage}%\n"

    # Defensive check: empty coverage list
    if not coverage.coverage_list:
      logging.warning("Coverage list is empty in format_coverage_summary")
      return summary + "\nNo coverage data available.\n"

    # Track type mismatches for debugging
    valid_entries = 0
    for file_cov in coverage.coverage_list:
      if isinstance(file_cov, FileCoverage):
        file_name = os.path.basename(file_cov.path)
        summary += (
          f"File: {file_name}\t"
          f"Lines: {file_cov.total_lines}\t"
          f"Covered: {file_cov.covered_lines}\t"
          f"Percent: {file_cov.coverage_pct:.2f}%\n"
        )
        valid_entries += 1
      else:
        logging.warning(f"Unexpected type in coverage_list: {type(file_cov).__name__}. Expected FileCoverage.")

    if valid_entries == 0:
      logging.error("No valid FileCoverage objects found in coverage_list")
      return summary + "\nError: Coverage data contains no valid FileCoverage objects.\n"

    return summary

  def extract_coverage_feedback(
      self, coverage: CoverageResponse, top_design_module: str, work_dir: str
  ) -> str:
    """
    Extract Verilator coverage feedback for LLM.

    Selects the best annotated source file (prioritizing files with most
    uncovered lines and control flow) and returns it with annotation legend.
    """
    import glob

    # Defensive check: empty coverage list
    if not coverage.coverage_list:
      logging.warning("Coverage list is empty in extract_coverage_feedback")
      return "Warning: No coverage data available to extract feedback."

    # Verify coverage_list contains FileCoverage objects
    has_file_coverage = any(isinstance(item, FileCoverage) for item in coverage.coverage_list)
    if not has_file_coverage:
      logging.error(f"No FileCoverage objects in coverage_list. Found types: {[type(item).__name__ for item in coverage.coverage_list]}")
      return "Error: Coverage data does not contain expected FileCoverage objects."

    # Find annotated directory - try multiple possible locations
    # First try the artifact_plan pattern with tb_stem
    import re
    annot_dir_candidates = [
      os.path.join(work_dir, "annotated"),  # Legacy location
    ]

    # Also check for tb_llm_*_annotated directories
    try:
      for item in os.listdir(work_dir):
        if item.endswith("_annotated") and os.path.isdir(os.path.join(work_dir, item)):
          annot_dir_candidates.append(os.path.join(work_dir, item))
    except (FileNotFoundError, PermissionError):
      pass

    annot_dir = None
    for candidate in annot_dir_candidates:
      if os.path.exists(candidate):
        annot_dir = candidate
        break

    if not annot_dir:
      return f"Error: No annotated directory found. Searched: {annot_dir_candidates}"

    # Select best file to show
    exclude_patterns = ["tb_*.sv", "*_tb.sv", "tb_*.v", "*_tb.v", "**/tests/**"]
    best_file = self._select_best_annotated_file(annot_dir, exclude_patterns)

    if not best_file:
      return f"Error: No annotated sources found under {annot_dir} (after exclusions)."

    try:
      with open(best_file, "r", encoding="utf-8", errors="ignore") as f:
        annotated_text = f.read()
    except FileNotFoundError:
      return f"Error: Could not open annotated file: {best_file}"

    annot_name = os.path.basename(best_file)

    legend = """\
How to read the Verilator annotated file:
- Each line has a prefix before the bar `|`.
  - A number like `   12 |` means the line executed 12 times (covered).
  - `##### |` means 0 hits (NOT covered).
  - `    - |` (dash or blank) means non-coverable (e.g., comments, braces).
Focus on lines marked `#####` to improve coverage."""

    return f"""Verilator-annotated source (selected for most uncovered lines): {annot_name}

{legend}

--------------------------------- BEGIN ANNOTATED SOURCE ---------------------------------
{annotated_text}
---------------------------------- END ANNOTATED SOURCE ----------------------------------

Important:
1. The test bench should ONLY target the top-level module {top_design_module}.
2. Use the annotated lines marked '##### |' (0 hits) as your primary targets.
3. Drive {top_design_module} inputs with sequences that exercise those uncovered lines."""

  def _select_best_annotated_file(
      self, annot_dir: str, exclude: list[str]
  ) -> str | None:
    """
    Select the best annotated file based on uncovered lines and control flow.

    Returns:
        Path to the best file, or None if no files found
    """
    import fnmatch

    # Find all files in annotated directory
    files = []
    for root, _, fnames in os.walk(annot_dir):
      for fn in fnames:
        # Ignore gcov byproducts
        if fnmatch.fnmatch(fn, "*.gcov"):
          continue

        path = os.path.normpath(os.path.join(root, fn))

        # Check exclude patterns
        excluded = False
        base = os.path.basename(path)
        for pat in exclude:
          if fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(base, pat):
            excluded = True
            break

        if not excluded:
          files.append(path)

    if not files:
      return None

    # Score each file
    scored_files = []
    for file_path in files:
      uncovered, cf_misses, total = self._score_annotated_file(file_path)

      if total == 0:
        continue

      # Composite score: prioritize uncovered lines and control flow
      score = uncovered * 1.0 + cf_misses * 3.0  # Weight control flow 3x
      scored_files.append((file_path, score))

    if not scored_files:
      return None

    # Return the file with highest score
    scored_files.sort(key=lambda x: x[1], reverse=True)
    return scored_files[0][0]

  @staticmethod
  def _score_annotated_file(file_path: str) -> tuple[int, int, int]:
    """
    Score an annotated file for selection priority.

    Returns:
        Tuple of (uncovered_lines_count, control_flow_misses, total_lines)
    """
    uncovered_count = 0
    control_flow_misses = 0
    total_lines = 0

    try:
      with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
          total_lines += 1
          # Verilator annotates with patterns like "##### |" for uncovered
          if line.startswith('#####'):
            uncovered_count += 1
            # Check if this is a control flow statement
            code_part = line.split('|', 1)[1] if '|' in line else line
            if re.search(r'\b(if|case|while|for)\s*\(', code_part):
              control_flow_misses += 1

    except (FileNotFoundError, IOError):
      return (0, 0, 0)

    return (uncovered_count, control_flow_misses, total_lines)


