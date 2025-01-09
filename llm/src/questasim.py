from subprocess import run, PIPE, TimeoutExpired
import datetime
import os
import logging
import shutil
from src.simulator import Simulator, CoverageResponse
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
        return self.run_command(compile_command)

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

    @staticmethod
    def parse_coverage_report(report_path: str) -> Tuple[List[dict], float]:
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

        for child in root[0]:
            coverage_dict = {'path': child.attrib['path']}
            coverage_dict['coverage'] = child[0].attrib
            coverage_dict['coverage_detail'] = [c.attrib for c in child[1:]]
            total_active += int(child[0].attrib['active'])
            total_hits += int(child[0].attrib['hits'])
            coverage_list.append(coverage_dict)

        total_coverage = (total_hits / total_active) * 100.0 if total_active > 0 else 0.0
        return coverage_list, total_coverage

    def run_sim(self, tb_path: str, data_point: dict, log_name: str) -> CoverageResponse:
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

        # Cleanup
        self.cleanup(design_dir)

        # Compilation
        try:
            compile_output = self.compile_design(tb_path, data_point)
            logging.info("Compilation successful.")
        except RuntimeError as e:
            return CoverageResponse(False, 1, str(e))

        # Simulation
        try:
            sim_output = self.run_simulation(tb_name, log_name)
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


    # Returns the path to the merged coverage ucdb
    # If an empty string is returned, there was an error merging the coverage
    def merge_coverage(coverage_dbs: list[Union[str, Path]]) -> str:

        if not all(isinstance(val, str) for val in coverage_dbs) and not all(isinstance(val, Path) for val in coverage_dbs):
            raise TypeError("Argument coverage_dbs should be a list of strings or Paths")

        for file in coverage_dbs:
            if os.path.isfile(file):
                raise ValueError("All file paths in coverage_dbs should be a valid path of a UCDB coverage database file")

        merge_coverage_result = run([f'{self.simulator_path}/vcover', 'merge', '-recursive', '-out', 'merged_coverage.ucdb'] + coverage_dbs, stdout=PIPE, stderr=PIPE)

        if not self.check_errors(merge_coverage_result):
            return ''

        if not os.path.isfile('merged_coverage.ucdb'):
            return ''

        return os.path.abspath('merged_coverage.ucdb')

        
    
    def check_errors(self, questa_output: str) -> bool:
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

    def get_makefile_design_compilation(self, makefile: str, questa_dir: str, design_dir: str) -> str:
        with open(makefile, 'r') as f:
            lines = f.readlines()

        compile_command = ''
        for idx, line in enumerate(lines):
            if "compile_design:" in line:
                compile_command = lines[idx + 2]
                break
        
        compile_command = compile_command.strip()
        compile_command = (compile_command.replace('$(QUESTA_ROOT)', questa_dir)).replace('$(BASE_DIR)', design_dir)

        return compile_command

    # TODO: Write Makefile parser
    def parse_makefile(self, makefile: str):
        pass

    def vlog_builder(self, tb_path: str, data_point: dict) -> str:
        return f"vlog -cover s {tb_path} {' '.join(data_point['design'])} {' '.join(data_point['design_context'])}"

    def merge_coverage(self, run_id: int):
        pass