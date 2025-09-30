import os
import logging
import re
from pathlib import Path

from llm_verif.simulator import Simulator, CoverageResponse, DU

logging.basicConfig(level=logging.INFO)

class Verilator(Simulator): 
  def __init__(self, simulator_path: str, design_unit: str):
    super().__init__(simulator_path, design_unit)

  def build_compile_command(self, testbench_path: str, data_point: dict) -> str:
    return f"{self.simulator_path}/verilator --binary -j 4 --coverage-line {testbench_path} {' '.join(data_point['design'])} {' '.join(data_point['design_context'])}"

  """
  COMPILE AND SIMULATE
  """

  def compile(self, testbench_path: str, data_point: dict) -> str:
    """
    Compile the design and testbench using Verilator.

    Args:
        testbench_path (str): Path to the testbench file.
        data_point (dict): Dictionary containing design and context files.
      
    Returns:
        str: Compilation output or error message.
    """

    compile_command = self.build_compile_command(testbench_path, data_point).split()
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
  
  def annotate_coverage(self, dat_path: str, report_path: str) -> str:
    
  
  def run_simulation_flow(self, work_dir: str | Path, tb_name: str, data_point: dict[str, str | list[str]] | None, log_name: str, sim_runs: int = 1) -> CoverageResponse:
    
    log_name = tb_name.split('.')[0]
    tb_path = os.path.join(work_dir, tb_name)
    compile_log_path = os.path.join(work_dir, f"{log_name}_compile.log")
    sim_log_path = os.path.join(work_dir, f"{log_name}_sim.log")
    coverage_dat_path = os.path.join(work_dir, f"{log_name}_coverage.dat")
    coverage_report_path = os.path.join(work_dir, f"{log_name}_coverage_report.txt")

