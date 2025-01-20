from subprocess import run, PIPE, TimeoutExpired
import datetime
import os
import logging
import shutil
from src.simulator import Simulator, CoverageResponse, DU
import re
from typing import Union, Dict, List
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple

logging.basicConfig(level=logging.INFO)

class QuestaSim(Simulator):

    def __init__(self, simulator_path: str):
        super().__init__(simulator_path)
    
    @staticmethod
    def run_command(command: List[str], log_file: str = None, timeout: int = None) -> str:
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
        """
        Cleanup temporary simulation files.

        Args:
            directory (str): Directory containing temporary files.
        """
        try:
            shutil.rmtree(os.path.join(directory, "work"), ignore_errors=True)
            os.remove(os.path.join(directory, "transcript"))
        except FileNotFoundError:
            pass
        except Exception as e:
            logging.warning(f"Error during cleanup: {e}")

    def compile_design(self, tb_path: str, data_point: dict) -> str:
        """
        Compile the design files.

        Args:
            tb_path (str): Path to the testbench file.
            data_point (dict): Data point for the simulation.

        Returns:
            str: Compilation output.
        """
        compile_command = self.vlog_builder(tb_path=tb_path, data_point=data_point)
        return self.run_command([compile_command])

    def run_simulation(self, tb_name: str, log_name: str) -> str:
        """
        Run the simulation.

        Args:
            tb_name (str): Testbench module name.
            log_name (str): Log file name.

        Returns:
            str: Simulation output.
        """
        questa_dir = self.simulator_path
        command = [
            f'{questa_dir}/vsim',
            f'work.{tb_name}',
            '-coverage',
            '-c',
            '-do',
            f'coverage exclude -du {tb_name};coverage save -onexit {log_name}.ucdb;run -all;exit;'
        ]
        return self.run_command(command, timeout=300)

    def generate_coverage_report(self, log_name: str) -> str:
        """
        Generate the coverage report.

        Args:
            log_name (str): Log file name.

        Returns:
            str: Report generation output.
        """
        questa_dir = self.simulator_path
        command = [
            f'{questa_dir}/vsim',
            '-viewcov',
            f'{log_name}.ucdb',
            '-c',
            '-do',
            f'coverage report -output {log_name}_report.txt -du=* -detail -annotate -code s -xml;exit;'
        ]
        return self.run_command(command)
    
    def generate_merged_coverage_ucdb(self, du: str, coverage_dbs: List[str], log_name: str) -> str:
        """
        Generate the coverage report.

        Args:
            du (str): Name of the design unit to be merged
            coverage dbs (List[str]): List of UCDB coverage databases to merge together.
            log_name (str): Log file name.

        Returns:
            str: Report generation output.
        """

        questa_dir = self.simulator_path
        command = [
            f'{questa_dir}/vcover',
            'merge',
            '-du',
            f'{du}'
            '-recursive'
            '-out',
            f'{log_name}.ucdb',
        ] + coverage_dbs

        return self.run_command(command)

    @staticmethod
    def parse_coverage_report(report_path: str) -> tuple[list[DU], float]:
        """
        Parse the coverage report XML and extract coverage details.

        Args:
            report_path (str): Path to the XML report file.

        Returns:
            Tuple[List[dict], float]: List of coverage details and total coverage percentage.
        """
        xml_tree = ET.parse(report_path)
        root = xml_tree.getroot()

        coverage_list = []
        total_active = 0
        total_hits = 0

        for du_data in root.findall('.//DuData'):
            du_name = du_data.get('du')
            file_map = du_data.find('.//fileMap')
            file_path = file_map.get('path') if file_map is not None else "unknown"

            statements = du_data.find('statements')
            active =  int(statements.get('active', 0)) if statements else 0
            hits = int(statements.get('hits', 0)) if statements else 0
            percent = float(statements.get('percent', 0.0)) if statements else 0
            
            details = du_data.findall('.//stmt')

            total_active += active 
            total_hits += hits

            coverage_list.append(DU(
                path=str(file_path),
                du=str(du_name),
                coverage={
                    'active': active,
                    'hits': hits,
                    'percent': percent
                },
                coverage_details=details
            ))

        total_coverage = (total_hits / total_active) * 100.0 if total_active > 0 else 0.0
        return coverage_list, total_coverage

    def run_sim(self, tb_path: str, data_point: dict[str, str | list[str]] | None, log_name: str) -> CoverageResponse:
        """
        Run the simulation and generate the coverage report.

        Args:
            tb_path (str): Path to the testbench file.
            data_point (dict): Data point for the simulation.
            log_name (str): Log file name.

        Returns:
            CoverageResponse: Response containing coverage data.
        """
        if not os.path.exists(tb_path):
            raise ValueError(f"Testbench path does not exist: {tb_path}")
        if not data_point:
            raise ValueError("Data point is required for simulation.")

        questa_dir = self.simulator_path
        design_dir = os.path.split(os.path.split(tb_path)[0])[0]
        tb_name = self.get_testbench_name(tb_path)

        # Check for $finish in the testbench
        if not self.has_finish(tb_path):
            return CoverageResponse(False, 5, "No $finish found in the test bench. Simulation will not finish.")

        # Cleanup
        self.cleanup(design_dir)

        # Compilation
        try:
            compile_output = self.compile_design(tb_path, data_point)
            with  open(f'{log_name}_compile.log', 'w') as f:
                f.write(compile_output)
            if not QuestaSim.check_errors(compile_output):
                raise RuntimeError(compile_output)
            logging.info("Compilation successful.")
        except RuntimeError as e:
            return CoverageResponse(False, 1, str(e))

        # Simulation
        try:
            sim_output = self.run_simulation(tb_name, log_name)
            with open(f'{log_name}_sim.log', 'w') as f:
                f.write(sim_output)
            if not QuestaSim.check_errors(sim_output):
                raise RuntimeError(sim_output)
            logging.info("Simulation successful.")
        except RuntimeError as e:
            return CoverageResponse(False, 2, str(e))

        # Coverage Report
        try:
            self.generate_coverage_report(log_name)
            coverage_list, total_coverage = self.parse_coverage_report(f'{log_name}_report.txt')
            logging.info("Coverage report generated successfully.")
            return CoverageResponse(True, 0, sim_output, coverage_list, total_coverage)
        except RuntimeError as e:
            return CoverageResponse(False, 3, str(e))

    def generate_merged_coverage_report(
        self, du: str, coverage_dbs: list[str], log_name: str
    ) -> str:
        """
        Generate a merged coverage XML report for a specific design unit.

        This method combines multiple coverage databases (`.ucdb` files) into a single coverage
        report and generates a detailed XML coverage report for the specified design unit.

        Args:
            du (str): The name of the design unit to generate the report for.
            coverage_dbs (List[Union[str, Path]]): A list of paths to coverage databases (`.ucdb` files).
            log_name (str): The base name of the log files to be generated.

        Returns:
            str: The output of the generated XML coverage report.

        Raises:
            TypeError: If `coverage_dbs` is not a homogeneous list of strings or Paths.
            RuntimeError: If an error occurs during the merging or report generation process.
        """
        # Validate input
        if not all(isinstance(val, (str, Path)) for val in coverage_dbs):
            raise TypeError("Argument coverage_dbs should be a list of strings or Paths.")

        try:
            # Merge coverage databases
            merge_output = self.generate_merged_coverage_ucdb(du, coverage_dbs, log_name)
            if not QuestaSim.check_errors(merge_output):
                raise RuntimeError(f"Error during UCDB merge: {merge_output}")

            # Generate the coverage report
            report_output = self.generate_coverage_report(log_name)
            return report_output
        except Exception as e:
            # Propagate exception for the caller to handle
            raise RuntimeError(f"Failed to generate merged coverage report: {e}") from e


    @staticmethod
    def check_errors(questa_output: str) -> bool:
        if not questa_output:
            return False

        lines = questa_output.splitlines()
        split_line = re.split(r'[#,:]', lines[-1])
        stripped_items = [item.strip() for item in split_line]
        cleaned_items = [x for x in stripped_items if x]
        print(cleaned_items)
        
        if len(cleaned_items) != 4:
            return False

        if cleaned_items[0] == 'Errors' and cleaned_items[1] == '0': #and cleaned_items[2] == 'Warnings' and cleaned_items[3] == '0':
            return True

        return False

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

    def vlog_builder(self, tb_path: str, data_point: dict) -> str:
        return f"vlog -cover s {tb_path} {' '.join(data_point['design'])} {' '.join(data_point['design_context'])}"

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
