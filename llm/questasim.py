from subprocess import run, PIPE
import datetime
import os
from storage import FileStore
from environment import Environment
import re
from typing import Union

def run_questasim(env: Union[Environment, str], tb_path: str, log_file: str, storage: FileStore = None) -> (bool, str):
    # Get the name of the test bench module
    # We need to do this because the LLM could name the module anything

    questa_dir = ''
    if isinstance(env, Environment):
        questa_dir = questa_dir
    elif isinstance(env, str):
        questa_dir = env
    else:
        return ''

    design_dir = os.path.split(tb_path)[0]

    tb_file = open(tb_path, 'r')
    tb_content = tb_file.readlines()
    tb_name = ''
    for line in tb_content:
        if line.find('module') != -1:
            split_line = re.split(r'[\W+]', line)
            tb_name = split_line[1]
            break
    tb_file.close()

    # Run the simulation and log the output
    with open(log_file, 'w+') as f:
        f.write(f"--- QuestaSim Simulation: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        f.flush()
        # run(['make', 'clean', 'all'], stdout=f, stderr=f)
    run(['rm', '-rf', f'{design_dir}/work', 'work', 'transcript'])
    
    compile_output = run([f'{questa_dir}/vlog', '-cover', 's'] + [os.path.join(design_dir, path) for path in os.listdir(design_dir)], stdout=PIPE, stderr=PIPE)
    if not check_errors(compile_output.stdout.decode()):
        return False, compile_output.stdout.decode()

    sim_output = run([f'{questa_dir}/vsim', f'work.{tb_name}', '-coverage', '-c', '-do', f'coverage exclude -du {tb_name};coverage save -onexit coverage.ucdb;run -all;exit;'], stdout=PIPE, stderr=PIPE)
    if not check_errors(sim_output.stdout.decode()):
        return False, compile_output.stdout.decode()

    report_output = run([f'{questa_dir}/vcover', 'report', 'coverage.ucdb'], stdout=PIPE, stderr=PIPE)
    if not check_errors(report_output.stdout.decode()):
        return False, report_output.stdout.decode()

    return True, report_output.stdout.decode()
    

def check_errors(questa_output: str) -> bool:
    lines = questa_output.splitlines()
    split_line = re.split(r'[#,:]', lines[-1])
    stripped_items = [item.strip() for item in split_line]
    cleaned_items = [x for x in stripped_items if x]
    print(cleaned_items)
    
    if len(cleaned_items) != 4:
        return False

    if cleaned_items[0] == 'Errors' and cleaned_items[1] == '0' and cleaned_items[2] == 'Warnings' and cleaned_items[3] == '0':
        return True

    return False