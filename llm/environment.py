from pathlib import Path
from dashboard import Dataset
from storage import FileStore
import os

class Environment:

    def __init__(self, questa_dir: str, design_dir: str):
        self.questa_dir = questa_dir
        self.design_dir = design_dir
        self.design_name = os.path.split(self.design_dir)[1]
        self.design_dir_path = Path(self.design_dir)
        self.dashboard_path = f'{str(self.design_dir_path.parents[1])}/dashboard.json'

        self.dataset = Dataset(self.dashboard_path)

        # Create the prompt
        # Read the specification file
        # TODO: Add support for PDF specification files/documentation
        self.design_specification_path = self.dataset.get_design_spec(design_name)
        self.design_specification = ''
        if not self.design_specification_path:
            print("Error: No design specification avaliable for this design")
            exit()
        elif isinstance(self.design_specification_path, list):
            # Here we assume the top item in the spec tag is the correct specification
            # This should not really happen because there should only be one specification file in the spec tag
            with open(self.design_specification_path[0], 'r') as spec:
                self.design_specification = spec.read()
        else:
            with open(self.design_specification_path, 'r') as spec:
                self.design_specification = spec.read()

        self.top_design_file_path = dataset.get_design(design_name)
        self.module_header = ''
        if not self.top_design_file_path:
            print("Error: No design file(s) avaliable for this design")
            exit()
        elif isinstance(self.top_design_file_path, list):
            # Here we assume the top item in the spec tag is the correct specification
            # This should not really happen because there should only be one specification file in the spec tag
            self.top_design_file_path = self.top_design_file_path[0]
            self.module_header = chat.extract_verilog_module_header(self.top_design_file_path)
        else:
            self.module_header = chat.extract_verilog_module_header(self.top_design_file_path)

        self.design_module_name = chat.get_design_name(self.top_design_file_path)

        self.store = FileStore('./generations')
        self.tokenizer = chat.load_model()

