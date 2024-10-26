from subprocess import run, PIPE, TimeoutExpired
import datetime
import os
from storage import FileStore
from environment import Environment
import re
from typing import Union, Dict
import xml.etree.ElementTree as ET
from dashboard import Dataset

class CoverageResponse:
    def __init__(self, success: bool, error_code: int, error_message: str = "", coverage_list: List[Dict[str, str]] = [], total_coverage: int = 0):
        self.success = success
        self.error_code = error_code
        self.error_message = error_message
        self.coverage_list = coverage_list
        self.total_coverage = total_coverage

def run_questasim(env: Union[Environment, str], tb_path: str, data_point: dict, log_file: str) -> (bool, int, str):
    # Get the name of the test bench module
    # We need to do this because the LLM could name the module anything

    questa_dir = ''
    if isinstance(env, Environment):
        questa_dir = questa_dir
    elif isinstance(env, str):
        questa_dir = env
    else:
        return ''

    design_dir = os.path.split(os.path.split(tb_path)[0])[0]

    tb_name = get_testbench_name(tb_path)

    compile_command = vlog_builder(tb_path=tb_path, data_point=data_point)

    # Run the simulation and log the output
    # with open(log_file, 'w+') as f:
    #   f.write(f"--- QuestaSim Simulation: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    #   f.flush()
    #        # run(['make', 'clean', 'all'], stdout=f, stderr=f)
    run(['rm', '-rf', f'{design_dir}/work', 'work', 'transcript'])
    
    # TODO: adapt for other designs
    # compile_output = run([f'{questa_dir}/vlog', '-cover', 's'] + [os.path.join(design_dir, path) for path in os.listdir(design_dir)], stdout=PIPE, stderr=PIPE)
    print(compile_command.split())
    compile_output = run(compile_command.split(), stdout=PIPE, stderr=PIPE)
    if not check_errors(compile_output.stdout.decode()):
        return CoverageResponse(False, 1, compile_output.stdout.decode())

    compile_output = run([f'{questa_dir}/vlog', '-cover', 's', tb_path], stdout=PIPE, stderr=PIPE)
    if not check_errors(compile_output.stdout.decode()):
        return CoverageResponse(False, 1, compile_output.stdout.decode())

    try:
        sim_output = run([f'{questa_dir}/vsim', f'work.{tb_name}', '-coverage', '-c', '-do', f'coverage exclude -du {tb_name};coverage save -onexit coverage.ucdb;run -all;exit;'], stdout=PIPE, stderr=PIPE, timeout=60*5)
        if not check_errors(sim_output.stdout.decode()):
            return CoverageResponse(False, 2, sim_output.stdout.decode())
    except TimeoutExpired:
        return CoverageResponse(False, 3, "Simulation timeout")

    """
    report_output = run([f'{questa_dir}/vcover', 'report', 'coverage.ucdb'], stdout=PIPE, stderr=PIPE)
    if not check_errors(report_output.stdout.decode()):
        return CoverageResponse(False, 4, report_output.stdout.decode())
    """

    report_output = run([f'{questa_dir}/vsim', '-viewcov', 'coverage.ucdb', '-c', '-do', f'coverage report -output report.txt -srcfile=* -detail -all -dump -annotate -option -assert -directive -cvg -codeAll -xml;exit;'], stdout=PIPE, stderr=PIPE)

    xml_tree = ET.parse('report.txt')
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

    total_coverage = (total_hits / total_active) * 100.0

    # Clean up
    os.remove("coverage.ucdb")
    os.remove("report.txt")

    return CoverageResponse(True, 0, report_output.stdout.decode(), coverage_list, total_coverage)
    

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

def get_testbench_name(tb_path: str) -> str:
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

def get_makefile_design_compilation(makefile: str, questa_dir: str, design_dir: str) -> str:
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
def parse_makefile(makefile: str):
    pass

def vlog_builder(tb_path: str, data_point: dict) -> str:
    return f"vlog -cover s {tb_path} {' '.join(data_point['design'])} {' '.join(data_point['design_context'])}"