import subprocess

def run_questasim(do_file: str):
    subprocess.run(['make', 'all'])
    

