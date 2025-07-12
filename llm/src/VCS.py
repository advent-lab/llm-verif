from subprocess import run, PIPE, TimeoutExpired
import datetime
import os
import logging
import shutil
from simulator import Simulator, CoverageResponse, DU
import re
from typing import Union, Dict, List
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple
import paramiko

logging.basicConfig(level=logging.INFO)

class VCS(Simulator):
    remote_host = "10.218.100.195" # This is Polaris's IP address

    def __init__(self, simulator_path: str, username: str, password: str):
        super().__init__(simulator_path)
        self.username = username
        self.password = password
    
    @staticmethod
    def run_command(commands: str, ssh: paramiko.SSHClient, log_file: str = None, timeout: int = None) -> str:
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
            # Run the commands on Polaris
            stdin, stdout, stderr = ssh.exec_command(commands)
            output = stdout.read().decode()

            if log_file:
                with open(log_file, 'w') as f:
                    f.write(output)
            return output
        except TimeoutExpired:
            raise RuntimeError(f"Command(s) {(commands)} timed out.")
        except Exception as e:
            raise RuntimeError(f"Failed to execute {(commands)}: {e}")
        

    @staticmethod
    def cleanup(directory: str):
        """
        Cleanup temporary simulation files.

        Args:
            directory (str): Directory containing temporary files.
        """
       

    def compile_design(self, tb_path: str, data_point: dict) -> str:
        """
        Compile the design files.

        Args:
            tb_path (str): Path to the testbench file.
            data_point (dict): Data point for the simulation.

        Returns:
            str: Compilation output.
        """

        set_up_commands = "cd /mnt/vault0/ehilaneh/temp_dir && source /mnt/vault0/ehilaneh/vcs_env.sh && export BASE_DIR=/mnt/vault0/ehilaneh/data_points"
        compile_command = self.vcs_builder(self.get_testbench_filename(tb_path), data_point)
        commands = f"{set_up_commands} && {compile_command}"

        ssh = self.ssh_connect()
        
        # Run the commands on Polaris
        compile_output = self.run_command(commands, ssh)

        self.ssh_disconnect(ssh)

        #return self.run_command(compile_command)
        return compile_output


    def run_simulation(self, tb_name: str) -> str:
        """
        Run the simulation.

        Args:
            tb_name (str): Testbench module name.
            log_name (str): Log file name.

        Returns:
            str: Simulation output.
        """
        testbench_filename = self.get_testbench_filename(tb_name)
        vdb_name = testbench_filename[:-2]
        set_up_commands = "cd /mnt/vault0/ehilaneh/temp_dir && source /mnt/vault0/ehilaneh/vcs_env.sh && export BASE_DIR=/mnt/vault0/ehilaneh/data_points"
        sim_command = f"./simv -cm line"
        commands = f"{set_up_commands} && {sim_command}"

        ssh = self.ssh_connect()
        
        # Run the commands on Polaris
        sim_output = self.run_command(commands, ssh)

        self.ssh_disconnect(ssh)

        #return self.run_command(compile_command)
        return sim_output

    def generate_coverage_report(self, log_name: str) -> str:
        """
        Generate the coverage report.

        Args:
            log_name (str): Log file name.

        Returns:
            str: Report generation output.
        """
        set_up_commands = "cd /mnt/vault0/ehilaneh/temp_dir && source /mnt/vault0/ehilaneh/vcs_env.sh && export BASE_DIR=/mnt/vault0/ehilaneh/data_points"
        coverage_report_cmd = "urg -dir test.vdb -format text -metric line -full64"
        commands = f"{set_up_commands} && {coverage_report_cmd}"
        
        ssh = self.ssh_connect()
        
        # Run the commands on Polaris
        cm_output = self.run_command(commands, ssh)

        self.ssh_disconnect(ssh)
        
        return ""
        
    
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

    @staticmethod
    def parse_coverage_report(report_path: str) -> tuple[list[DU], float]:
        """
        Parse the coverage report XML and extract coverage details.

        Args:
            report_path (str): Path to the XML report file.

        Returns:
            Tuple[List[dict], float]: List of coverage details and total coverage percentage.
        """
       

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
       
    def send_tb(self, tb_path: str):
        """
        Make a directory on the polaris server and send the files needed for compilation and simulation.

        Args:
            tb_path (str): Path to the testbench file.

        Returns:
            bool: True if the files were sent successfully, false otherwise.
        """
        ssh = self.ssh_connect()

        # Create a directory on Polaris for compilation and simulation
        stdin, stdout, stderr = ssh.exec_command("mkdir /mnt/vault0/ehilaneh/temp_dir")

        # Use SFTP to transfer the testbench to Polaris
        sftp = ssh.open_sftp()
        sftp.put(tb_path, f"/mnt/vault0/ehilaneh/temp_dir/{self.get_testbench_filename(tb_path)}")
        sftp.close()

        self.ssh_disconnect(ssh)

    def ssh_connect(self) -> paramiko.SSHClient:
        """
        Connect to the Polaris server via ssh.

        Args:
            remote_host (String): Location of the remote server.
            username (String): The username to be used for logging in (asurite).
            password (String): The password corresponding to the asurite username.

        Returns:
            SSHClient: The SSHClient variable associated with the connection.
        """
        #connect to polaris via ssh
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        #sign in using username/password
        ssh.connect(hostname=self.remote_host, username=self.username, password=self.password)

        return ssh

    def ssh_disconnect(self, ssh: paramiko.SSHClient):
        ssh.close()

    @staticmethod
    def check_errors(vcs_output: str) -> bool:
        if not vcs_output:
            return False

        lines = vcs_output.splitlines()
        split_line = re.split(r'[#,:]', lines[-1])
        stripped_items = [item.strip() for item in split_line]
        cleaned_items = [x for x in stripped_items if x]
        
        if len(cleaned_items) != 3:
            return False

        if cleaned_items[1] == '0 error(s)':
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

    def get_testbench_filename(self, tb_path: str) -> str:
        slash_index = tb_path.rfind("/")
        tb_filename = tb_path[(slash_index + 1):]
        return tb_filename

    def vcs_builder(self, tb_path: str, data_point: dict) -> str:
        return f"vcs {tb_path} {' '.join(data_point['design'])} {' '.join(data_point['design_context'])} -cm line -cm_dir test.vdb -full64 -sverilog -debug_access+all -kdb"

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

vcs_simulator = VCS("", "ehilaneh@ASUAD", "Macrina23*")
tb_path = "/scratch/ehilaneh/runs/activation_constant_temperature_0/tb_llm_activation_0_7_0.v"
tb_path2 = "/scratch/ehilaneh/runs/simple_mat_mul_constant_batch_3/tb_llm_simple_mat_mul_0_11_4.v"
tb_path3 = "/scratch/ehilaneh/runs/chacha_top_constant_batch_11/tb_llm_chacha_top_0_0_0.v"
data_point = {
    "verif": [],
    "verif_context": [],
    "design": ["$BASE_DIR/activation/design/design.v"],
    "design_context": [],
    "spec": ["$BASE_DIR/activation/spec/spec.txt"],
    "makefile": ["$BASE_DIR/activation/questa/Makefile"]
}
data_point2 = {
    "verif": [],
    "verif_context": [],
    "design": [
        "$BASE_DIR/simple_mat_mul/design/design.v"
    ],
    "design_context": [],
    "spec": [
        "$BASE_DIR/simple_mat_mul/spec/spec.txt"
    ],
    "makefile": [
        "$BASE_DIR/simple_mat_mul/questa/Makefile"
    ]
}
data_point3 = {
    "verif": [
        "$BASE_DIR/chacha_top/verif/tb_chacha.v"
    ],
    "verif_context": [],
    "design": [
        "$BASE_DIR/chacha_top/design/chacha.v"
    ],
    "design_context": [
        "$BASE_DIR/chacha_top/design_context/chacha_core.v",
        "$BASE_DIR/chacha_top/design_context/chacha_qr.v"
    ],
    "spec": [
        "$BASE_DIR/chacha_top/spec/spec.md"
    ],
    "makefile": [
        "$BASE_DIR/chacha_top/questa/Makefile"
    ]
}

vcs_simulator.send_tb(tb_path)
compile_output = vcs_simulator.compile_design(tb_path, data_point)
print(compile_output)
simulation_output = vcs_simulator.run_simulation(tb_path)
print(simulation_output)
errors = VCS.check_errors(compile_output)
print(errors)
string = vcs_simulator.generate_coverage_report("")
