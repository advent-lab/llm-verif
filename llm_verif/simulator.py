from dataclasses import dataclass
from pathlib import Path
from subprocess import PIPE, TimeoutExpired, run
from typing import List, Sequence
from xml.etree.ElementTree import Element

from llm_verif.verilator_coverage_util import FileCoverage

@dataclass
class DU:
    path: str
    du: str
    coverage: dict[str, int | float]
    coverage_details: list[Element]

@dataclass
class CoverageResponse:
        
    success: bool
    error_code: int
    error_message: str
    coverage_list: Sequence[DU | FileCoverage] = []
    total_coverage: float = 0.0
    
    # Error codes
    # -1: empty object
    # 0: success -> ignore error message
    # 1: compile error
    # 2: simulation error
    # 3: simulation timeout
    # 4: JSON Decode error -> incomplete testbench
    # 5: No $finish found -> LLM did not generate finish in test bench. Avoids running a test bench that will not finish

class Simulator():

    def __init__(self, simulator_path: str, design_unit: str):
        self.simulator_path = simulator_path
        self.design_unit = design_unit

    """
    Generic method for running commands
    """
    @staticmethod
    def run_command(command: List[str], log_file: str | None = None, timeout: int | None = None) -> str:
        """
        Run a command in the shell and capture its output.

        Args:
            command (List[str]): The command to execute.
            log_file (str, optional): File to log the output.
            timeout (int, optional): Timeout in seconds.

        Returns:
            str: Standard output of the command.

        Raises:
            RuntimeError: If the command fails or times out.
        """
        try:
            result = run(command, stdout=PIPE, stderr=PIPE, timeout=timeout)
            output = result.stdout.decode()
            if log_file:
                with open(log_file, 'w') as f:
                    f.write(output)
            return output
        except TimeoutExpired:
            raise RuntimeError(f"Command {' '.join(command)} timed out.")
        except Exception as e:
            raise RuntimeError(f"Failed to execute {' '.join(command)}: {e}")

    @staticmethod
    def cleanup(directory: str):
        raise NotImplementedError("This method should be implemented by subclasses.") 

    def run_simulation_flow(self, work_dir: str | Path, tb_name: str, data_point: dict[str, str | list[str]] | None, log_name: str, sim_runs: int = 1) -> CoverageResponse:
        """Run the simulation - to be overridden by subclasses"""
        raise NotImplementedError("This method should be implemented by subclasses.")
    
    def generate_merged_coverage_report(self, du: str, coverage_dbs: list[str], coverage_ucdb_path: str, coverage_report_path: str) -> str:
        """Generate merged coverage report - to be overridden by subclasses"""
        raise NotImplementedError("This method should be implemented by subclasses.")
    
    def merge_coverage(self) -> str:
        """Merge coverage - to be overridden by subclasses"""
        raise NotImplementedError("This method should be implemented by subclasses.")
    
    def get_testbench_name(self, tb_path: str) -> str:
        with open(tb_path, 'r') as tb_file:
            tb_content = tb_file.readlines()
            tb_name = ''
            for line in tb_content:
                if line.find('module') != -1:
                    split_line = re.split(r'[\W+]', line)
                    stripped_items = [item.strip() for item in split_line]
                    cleaned_items = [x for x in stripped_items if x]
                    return cleaned_items[-1]

        return ''
    
    def has_finish(self, file_path):
        """
        Checks if '$finish' is present in a Verilog test bench file.
        
        Args:
            file_path (str): Path to the Verilog test bench file.
        
        Returns:
            bool: True if '$finish' is found, False otherwise.
        """
        finish_pattern = re.compile(r'\$finish\b')

        try:
            with open(file_path, 'r') as file:
                for line in file:
                    if finish_pattern.search(line):
                        return True
        except FileNotFoundError:
            print(f"Error: File not found - {file_path}")
            return False

        return False