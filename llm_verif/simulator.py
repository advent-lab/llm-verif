from pathlib import Path
from subprocess import PIPE, TimeoutExpired, run
from typing import List
from xml.etree.ElementTree import Element

class DU:
    def __init__(self, path: str, du: str, coverage: dict[str, int | float], coverage_details: list[Element]) -> None:
        self.path: str
        self.du: str
        self.coverage: dict[str, int | float]
        self.coverage_details: list[Element]

        self.path = path
        self.du = du
        self.coverage = coverage
        self.coverage_details = coverage_details

class CoverageResponse:
    def __init__(self, success: bool = False, error_code: int = -1, error_message: str = "", coverage_list: list[DU] = [], total_coverage: float = 0):
        
        self.success: bool
        self.error_code: int
        self.error_message: str
        self.coverage_list: list[DU]
        self.total_coverage: float
        
        self.success = success
        # Error codes
        # -1: empty object
        # 0: success -> ignore error message
        # 1: compile error
        # 2: simulation error
        # 3: simulation timeout
        # 4: JSON Decode error -> incomplete testbench
        # 5: No $finish found -> LLM did not generate finish in test bench. Avoids running a test bench that will not finish
        self.error_code = error_code
        self.error_message = error_message
        self.coverage_list = coverage_list
        self.total_coverage = total_coverage

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