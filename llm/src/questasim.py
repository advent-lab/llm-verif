from subprocess import run, PIPE, TimeoutExpired
import datetime
import os
from src.simulator import Simulator, CoverageResponse
import re
from typing import Union, Dict, List
import xml.etree.ElementTree as ET
from pathlib import Path

class QuestaSim(Simulator):

    def __init__(self, simulator_path: str):
        super().__init__(simulator_path)
    
    def run_sim(self, tb_path: str, data_point: dict, log_name: str) -> CoverageResponse:
        # Get the name of the test bench module
        # We need to do this because the LLM could name the module anything

        questa_dir = self.simulator_path

        design_dir = os.path.split(os.path.split(tb_path)[0])[0]

        tb_name = self.get_testbench_name(tb_path)

        compile_command = self.vlog_builder(tb_path=tb_path, data_point=data_point)

        # Run the simulation and log the output
        # with open(log_file, 'w+') as f:
        #   f.write(f"--- QuestaSim Simulation: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        #   f.flush()
        #        # run(['make', 'clean', 'all'], stdout=f, stderr=f)
        run(['rm', '-rf', f'{design_dir}/work', 'work', 'transcript'])
        
        
        # TODO: adapt for other designs
        # compile_output = run([f'{questa_dir}/vlog', '-cover', 's'] + [os.path.join(design_dir, path) for path in os.listdir(design_dir)], stdout=PIPE, stderr=PIPE)
        print(compile_command.split())
        compile_output0 = run(compile_command.split(), stdout=PIPE, stderr=PIPE)
        if not self.check_errors(compile_output0.stdout.decode()):
            return CoverageResponse(False, 1, compile_output0.stdout.decode())

        compile_output1 = run([f'{questa_dir}/vlog', '-cover', 's', tb_path], stdout=PIPE, stderr=PIPE)

        compile_output = compile_output0.stdout.decode() + compile_output1.stdout.decode()

        with open(f'{log_name}_compile.log', 'w+') as f:
            f.write(compile_output) 
        

        if not self.check_errors(compile_output1.stdout.decode()):
            return CoverageResponse(False, 1, compile_output1.stdout.decode())

        try:
            sim_output = run([f'{questa_dir}/vsim', f'work.{tb_name}', '-coverage', '-c', '-do', f'coverage exclude -du {tb_name};coverage save -onexit {log_name}.ucdb;run -all;exit;'], stdout=PIPE, stderr=PIPE, timeout=60*5)
            
            with open(f'{log_name}_sim.log', 'w+') as f:
                f.write(sim_output.stdout.decode()) 
            
            if not self.check_errors(sim_output.stdout.decode()):
                return CoverageResponse(False, 2, sim_output.stdout.decode())
        except TimeoutExpired:

            with open(f'{log_name}_sim.log', 'w+') as f:
                f.write(sim_output.stdout.decode()) 

            return CoverageResponse(False, 3, "Simulation timeout")

        """
        report_output = run([f'{questa_dir}/vcover', 'report', 'coverage.ucdb'], stdout=PIPE, stderr=PIPE)
        if not check_errors(report_output.stdout.decode()):
            return CoverageResponse(False, 4, report_output.stdout.decode())
        """

        report_output = run([f'{questa_dir}/vsim', '-viewcov', f'{log_name}.ucdb', '-c', '-do', f'coverage report -output {log_name}_report.txt -srcfile=* -detail -all -dump -annotate -option -assert -directive -cvg -codeAll -xml;exit;'], stdout=PIPE, stderr=PIPE)

        xml_tree = ET.parse(f'{log_name}_report.txt')
        coverage_list = []
        root = xml_tree.getroot()

        total_active = 0
        total_hits = 0
        for child in root[0]:
            coverage_dict = {}
            attrib_list = []
            for cchild in child:
                attrib_list.append(cchild.attrib)

            coverage_dict['path'] = child.attrib['path']
            coverage_dict['coverage'] = attrib_list[0]
            coverage_dict['coverage_detail'] = attrib_list[1:]
            
            total_active = total_active + int(child[0].attrib['active'])
            total_hits = total_hits + int(child[0].attrib['hits'])

            coverage_list.append(coverage_dict)

        total_coverage = (total_hits / total_active) * 100.0

        return CoverageResponse(True, 0, report_output.stdout.decode(), coverage_list, total_coverage)

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