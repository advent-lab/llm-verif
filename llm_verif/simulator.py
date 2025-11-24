from dataclasses import dataclass, field
from pathlib import Path
from subprocess import PIPE, TimeoutExpired, run
from typing import Any, List, Sequence, Optional
from xml.etree.ElementTree import Element
import re
import logging

@dataclass(frozen=True)
class CoverageDB:
    path: str
    run_id: int

@dataclass(frozen=True)
class CoverageMergeResult:
    merged_db: Optional[str]
    report_path: Optional[str]
    annotate_dir: Optional[str]
    extra_paths: List[str]

@dataclass
class ArtifactPlan:
    work_dir: str
    tb_path: str
    compile_log: str
    sim_logs: List[str]
    per_run_coverage_dbs: List[str]
    merged_coverage_db: str
    report_path: str
    annotate_dir: Optional[str]
    info_path: Optional[str]

@dataclass
class DU:
    path: str
    du: str
    coverage: dict[str, int | float]
    coverage_details: list[Element]

@dataclass
class CoverageResponse:

    success: bool = False
    error_code: int = -1
    error_message: str = ""
    coverage_list: Sequence[Any] = field(default_factory=list)  # Simulator-specific: QuestaSim uses DU, Verilator uses FileCoverage
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
            str: Combined standard output and standard error of the command.

        Raises:
            RuntimeError: If the command fails or times out.
        """
        try:
            result = run(command, stdout=PIPE, stderr=PIPE, timeout=timeout)
            stdout = result.stdout.decode()
            stderr = result.stderr.decode()

            # Combine stdout and stderr for complete output
            output = stdout
            if stderr:
                output += "\n" + stderr

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

    def run_simulation_flow(self, work_dir: str | Path, tb_name: str, data_point: dict[str, str | list[str]] | None, sim_runs: int = 1) -> CoverageResponse:
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
    
    def has_finish(self, file_path) -> bool:
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
            logging.error(f"File not found - {file_path}")
            return False

        return False
    
    def plan_artifacts(self, work_dir: str | Path, tb_stem: str, sim_runs: int) -> ArtifactPlan:

        raise NotImplementedError("This method should be implemented by subclasses.")

    def get_coverage_file_extension(self) -> str:
        """
        Get the file extension for coverage database files.

        Returns:
            str: File extension (e.g., '.ucdb' for QuestaSim, '.dat' for Verilator)
        """
        raise NotImplementedError("This method should be implemented by subclasses.")
    
    def merge_and_parse_run_coverage(
        self, design_name: str, work_dir: str, run_idx: int, max_iterations: int,
        batch_size: int, sim_runs: int, design_dir: str, use_store: bool
    ) -> CoverageResponse:
        """
        Merge coverage for a specific run and parse the result.

        This is a high-level method that handles file collection, merging, and parsing
        in a simulator-agnostic way.

        Args:
            design_name: Name of the design module
            work_dir: Working directory containing coverage files
            run_idx: Index of the current run
            max_iterations: Maximum iterations per run
            batch_size: Batch size per iteration
            sim_runs: Number of simulation runs per testbench
            design_dir: Design directory path
            use_store: Whether using file store

        Returns:
            CoverageResponse: Response containing merged coverage data

        Raises:
            FileNotFoundError: If no coverage files are found
            RuntimeError: If merge or parse fails
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

    def merge_and_parse_cross_run_coverage(
        self, design_name: str, work_dir: str, runs: int, max_iterations: int,
        batch_size: int, sim_runs: int, design_dir: str, use_store: bool
    ) -> CoverageResponse:
        """
        Merge coverage across all runs and parse the result.

        This is a high-level method that handles file collection, merging, and parsing
        in a simulator-agnostic way.

        Args:
            design_name: Name of the design module
            work_dir: Working directory containing coverage files
            runs: Number of runs
            max_iterations: Maximum iterations per run
            batch_size: Batch size per iteration
            sim_runs: Number of simulation runs per testbench
            design_dir: Design directory path
            use_store: Whether using file store

        Returns:
            CoverageResponse: Response containing merged coverage data

        Raises:
            FileNotFoundError: If no coverage files are found
            RuntimeError: If merge or parse fails
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

    def format_coverage_summary(self, coverage: CoverageResponse) -> str:
        """
        Format a human-readable coverage summary from coverage response.

        Each simulator can format its coverage data in the most appropriate way
        for presentation to the LLM.

        Args:
            coverage: Coverage response to format

        Returns:
            Formatted string summarizing coverage
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

    def extract_coverage_feedback(
        self, coverage: CoverageResponse, top_design_module: str, work_dir: str
    ) -> str:
        """
        Extract coverage feedback to help LLM improve the next testbench.

        This method selects the most relevant coverage information (e.g., a specific
        uncovered module, an annotated source file) and formats it for the LLM.

        Args:
            coverage: Coverage response with coverage data
            top_design_module: Name of the top-level design module
            work_dir: Working directory (may contain annotated sources)

        Returns:
            Formatted feedback string with coverage holes and context
        """
        raise NotImplementedError("This method should be implemented by subclasses.") 
