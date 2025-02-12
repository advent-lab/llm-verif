# import sys
# sys.path.append('/home/asbabbit/llm_verif_dataset/llm_src')

from ast import Name
from pathlib import Path
from src.dashboard import Dataset
from src.storage import FileStore
import os
import re
from argparse import Namespace

class Environment:

    def __init__(self, env_options: Namespace):
        self.design_dir = env_options.design
        self.design_name = os.path.split(self.design_dir)[1]
        self.design_dir_path = Path(self.design_dir)
        self.dashboard_path = f'{str(self.design_dir_path.parents[1])}/dashboard.json'

        self.dataset = Dataset(self.dashboard_path)

        self.testplan = env_options.testplan

        # Create the prompt
        # Read the specification file
        # TODO: Add support for PDF specification files/documentation
        self.design_specification_path = self.dataset.get_design_spec(self.design_name)
        self.design_specification = ''
        if not self.design_specification_path:
            print("Error: No design specification avaliable for this design")
            exit()
        elif isinstance(self.design_specification_path, list):
            # Here we assume the top item in the spec tag is the correct specification
            # This should not really happen because there should only be one specification file in the spec tag
            for spec in self.design_specification_path:
                with open(spec, 'r') as f:
                    self.design_specification += f.read()
        else:
            with open(self.design_specification_path, 'r') as spec:
                self.design_specification = spec.read()

        self.top_design_file_path = self.dataset.get_design(self.design_name)
        self.all_design_file_paths = self.dataset.get_design_and_context(self.design_name)

        self.module_header = ''
        if not self.top_design_file_path:
            print("Error: No design file(s) avaliable for this design")
            exit()
        elif isinstance(self.top_design_file_path, list):
            # Here we assume the top item in the spec tag is the correct specification
            # This should not really happen because there should only be one specification file in the spec tag
            self.top_design_file_path = self.top_design_file_path[0]
            self.module_header = self.extract_verilog_module_header(self.top_design_file_path)
        else:
            self.module_header = self.extract_verilog_module_header(self.top_design_file_path)

        self.design_module_name = self.get_design_name(self.top_design_file_path)

        self.store = FileStore(args.output)

    def get_design_name(self, design_path: str) -> str:
        split_filename = os.path.split(design_path)[1].split('.')
        if len(split_filename) != 2:
            return ''

        if split_filename[1] != 'v':
            return ''

        return split_filename[0]

    def extract_verilog_module_header(self, design_path: str) -> str:
        # Read the file line by line to identify the header
        with open(design_path, 'r') as f:
            lines = f.readlines()

        start_line = None
        end_line = None
        inside_module = False
        capturing_ports = False

        # Loop through lines to find the module declaration and subsequent I/O declarations
        for i, line in enumerate(lines):
            # Look for the start of the module declaration
            if re.match(r"\s*module\s+\w+", line) and start_line is None:
                start_line = i
                inside_module = True

            # If we're inside the module header, check for the end of the main header
            if inside_module:
                # Detect the end of the main module header (closing parenthesis with semicolon)
                if re.search(r"\);\s*$", line):
                    end_line = i
                    inside_module = False
                    capturing_ports = True  # Start capturing additional ports after the header ends
                    continue

            # Capture subsequent input/output/inout declarations
            if capturing_ports:
                if re.match(r"\s*(input|output|inout|parameter)\s+", line):
                    end_line = i  # Update end line for each I/O declaration line

        # Slice the lines to get only the module header and subsequent I/O declarations
        if start_line is not None and end_line is not None:
            module_header = "".join(lines[start_line:end_line + 1])
            return module_header.strip()
        else:
            return "No module header found."

