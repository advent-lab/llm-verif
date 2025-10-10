import os
import logging
import re
from pathlib import Path

from llm_verif.simulator import Simulator, CoverageResponse, DU
from llm_verif.verilator_coverage_util import *

logging.basicConfig(level=logging.INFO)

class Verilator(Simulator): 
  def __init__(self, simulator_path: str, design_unit: str):
    super().__init__(simulator_path, design_unit)

  def build_compile_command(self, testbench_path: str, data_point: dict, coverage_dat_path: str) -> str:
    return f"{self.simulator_path}/verilator --binary -j 4 --coverage-line -Wno-fatal +verilator+coverage+file+{coverage_dat_path} {testbench_path} {' '.join(data_point['design'])} {' '.join(data_point['design_context'])}"

  """
  COMPILE AND SIMULATE
  """

  def compile(self, testbench_path: str, data_point: dict[str, str | list[str]], coverage_dat_path: str) -> str:
    """
    Compile the design and testbench using Verilator.

    Args:
        testbench_path (str): Path to the testbench file.
        data_point (dict): Dictionary containing design and context files.
      
    Returns:
        str: Compilation output or error message.
    """

    compile_command = self.build_compile_command(testbench_path, data_point, coverage_dat_path).split()
    return self.run_command(compile_command)
  
  def simulate(self, testbench_module: str, dat_path: str) -> str:
    """
    Simulate the compiled design using Verilator.

    Args:
        testbench_module (str): Name of the testbench module.
        dat_path (str): Path to the .dat file for simulation input.

    Returns:
        str: Simulation output or error message.
    """

    command = [
      f"./obj_dir/V{testbench_module}"
    ]

    return self.run_command(command, timeout=300)
  
  def run_simulation_flow(self, work_dir: str | Path, tb_name: str, data_point: dict[str, str | list[str]] | None, log_name: str, sim_runs: int = 1) -> CoverageResponse:
    
    log_name = tb_name.split('.')[0]
    tb_path = os.path.join(work_dir, tb_name)
    compile_log_path = os.path.join(work_dir, f"{log_name}_compile.log")
    sim_log_path = os.path.join(work_dir, f"{log_name}_sim.log")
    coverage_dat_path = os.path.join(work_dir, f"{log_name}_coverage.dat")
    coverage_report_path = os.path.join(work_dir, f"{log_name}_coverage_report.txt")
    coverage_info_path = os.path.join(work_dir, f"{log_name}_coverage_info.txt")
    coverage_annotate_dir_path = os.path.join(work_dir, f"annotated")

    design_dir = os.path.split(os.path.split(tb_name)[0])[0]
    tb_module_name = self.get_testbench_name(tb_path)

    if not self.has_finish(tb_path):
      logging.error(f"Testbench {tb_path} does not contain 'finish' statement.")
      return CoverageResponse(False, 5, "No $finish found in testbench", [], 0)
    
    self.cleanup(design_dir)

    try:
      compile_output = self.compile(tb_path, data_point) # type: ignore
      with open(compile_log_path, 'w') as f:
        f.write(compile_output)

      if Verilator.check_errors(compile_output):
        logging.error(f"Compilation error for {tb_path}. Check {compile_log_path} for details.")
        return CoverageResponse(False, 1, "Compilation error occurred", [], 0)
      
    except RuntimeError as e:
      logging.error(f"Compilation failed for {tb_path}: {e}")
      return CoverageResponse(False, 1, str(e), [], 0)
    
    dat_paths = []
    try:
      for i in range(sim_runs):
        sim_log_path_i = os.path.join(work_dir, f"{log_name}_{i}_sim.log")
        dat_path_i = os.path.join(work_dir, f"{log_name}_{i}_coverage.dat")
        dat_paths.append(dat_path_i)

        sim_output = self.simulate(tb_module_name, dat_path_i)
        with open(sim_log_path_i, 'w') as f:
          f.write(sim_output)
        
        if Verilator.check_errors(sim_output):
          logging.error(f"Simulation error for {tb_path}. Check {sim_log_path_i} for details.")
          raise RuntimeError(sim_output)
        
        logging.info(f"Simulation run {i+1}/{sim_runs} completed for {tb_path}.")

    except RuntimeError as e:
      logging.error(f"Simulation failed for {tb_path}: {e}")
      return CoverageResponse(False, 2, str(e), [], 0)
    
    try:
      self.generate_merged_coverage_report(self.design_unit, dat_paths, coverage_dat_path, coverage_annotate_dir_path)

      coverage_list, total_coverage = self.parse_coverage_report(coverage_info_path, tb_path)
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
    
  def generate_merged_coverage_report(self, du: str, coverage_dats: list[str], coverage_dat_path: str, annotated_dir_path: str):
      """
      Generate a merged coverage report from multiple .dat files.

      Args:
          du (str): Design unit name.
          coverage_dats (list[str]): List of .dat file paths to merge.
          coverage_dat_path (str): Path to save the merged .dat file.
          annotated_dir_path (str): Directory to save annotated source files.
      """

      merge_command = [
        f"{self.simulator_path}/verilator_coverage",
        "-write-info",
        coverage_dat_path,
        "--annotate",
        annotated_dir_path,
      ] + coverage_dats

      return self.run_command(merge_command)

  @staticmethod
  def parse_coverage_report(report_path: str, tb_path: str):
    file_coverage: list[FileCoverage] = load_file_coverage(report_path, exclude=[tb_path])
    total_lines, covered_lines, coverage_pct = total_coverage(file_coverage)

    return file_coverage, coverage_pct
  
  import re

  @staticmethod
  def check_errors(output: str) -> bool:
    """
    Return True if Verilator output indicates an error or fatal condition.
    Accepts stdout/stderr text from compilation or simulation.
    """
    return bool(re.search(r'\b%(?:Error|Fatal):', output))


