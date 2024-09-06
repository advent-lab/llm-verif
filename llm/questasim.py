import subprocess
import datetime
import os
from storage import FileStore

def run_questasim(makefile: str, log_file: str, storage: FileStore = None) -> str:
    # Move the Makefile to the current directory
    os.rename(makefile, 'Makefile')

    # Run the simulation and log the output
    with open(log_file, 'a+') as f:
        f.write(f"--- QuestaSim Simulation: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        subprocess.run(['make', 'all'], stdout=f)

        subprocess.run(['make', 'clean'], stdout=f)

    # Move the log file to the storage directory
    coverage_report_file = open('./coverage_report.txt', 'r+')
    coverage_report = coverage_report_file.read()

    if storage is not None:
        storage.move('./coverage.ucdb')
    
    os.remove('./coverage_report.txt')

    return coverage_report

def read_last_line(file_path):
    with open(file_path, 'rb') as f:
        # Move the pointer to the end of the file
        f.seek(-2, 2)  # Start at the second last byte in the file
        
        # Move backwards until you hit the start of the last line
        while f.read(1) != b'\n':
            f.seek(-2, 1)
        
        last_line = f.readline().decode()
        
    return last_line




    

