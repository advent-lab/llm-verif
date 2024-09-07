import subprocess
import datetime
import os
from storage import FileStore
from environment import Environment
import re

def run_questasim(env: Environment, tb_path: str, log_file: str, storage: FileStore = None) -> str:
    # Get the name of the test bench module
    # We need to do this because the LLM could name the module anything
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
        # subprocess.run(['make', 'clean', 'all'], stdout=f, stderr=f)
        subprocess.run(['rm', '-rf', f'{design_dir}/work', 'work', 'transcript'])
        subprocess.run([f'{env.questa_dir}/vlog', '-cover', 's'] + [os.path.join(design_dir, path) for path in os.listdir(design_dir)])
        subprocess.run([f'{env.questa_dir}/vsim', f'work.{tb_name}', '-coverage', '-c', '-do', 'questa_coverage.do'])
    
    captured_output = subprocess.run([f'{env.questa_dir}/vcover', 'report', 'covergae.ucdb'], capture_output=True)

    # Move the log file to the storage directory
    '''
    coverage_report_file = open('./coverage_report.txt', 'a+')
    coverage_report_file.seek(0,0)
    coverage_report = coverage_report_file.read()
    '''

    if storage is not None:
        storage.move('./coverage.ucdb')
    
    '''
    coverage_report_file.close()
    os.remove('./coverage_report.txt')
    '''

    return captured_output.stdout

def read_last_line(file_path):
    with open(file_path, 'rb') as f:
        # Move the pointer to the end of the file
        f.seek(-2, 2)  # Start at the second last byte in the file
        
        # Move backwards until you hit the start of the last line
        while f.read(1) != b'\n':
            f.seek(-2, 1)
        
        last_line = f.readline().decode()
        
    return last_line




    

