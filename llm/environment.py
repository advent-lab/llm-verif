from pathlib import Path
from dashboard import Dataset
from storage import FileStore
import os
import llama3_chat as chat

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

        self.store = FileStore('./generations')
        self.tokenizer = chat.load_model()

    def get_design_name(self, design_path: str) -> str:
        split_filename = os.path.split(design_path)[1].split('.')
        if len(split_filename) != 2:
            return ''

        if split_filename[1] != 'v':
            return ''

        return split_filename[0]

    def extract_verilog_module_header(self, design_path: str) -> str:

        # Open file and read design
        with open(design_path, 'r') as f:
            verilog_code = f.read()

        # Regular expression to capture the module name and header
        module_pattern = re.compile(
            r"module\s+(\w+)\s*\((.*?)\);\s*", 
            re.DOTALL
        )
        
        # Extracting module declaration
        match = module_pattern.search(verilog_code)
        if match:
            module_name = match.group(1)  # Module name
            port_list = match.group(2)    # Port list (inputs and outputs)

            # Cleaning up whitespace and formatting the result
            port_list = re.sub(r"\s+", " ", port_list.strip())  # Remove excessive whitespace
            formatted_ports = "\n    ".join(port_list.split(","))  # Format each port on a new line

            # Return formatted header
            return f"module {module_name}(\n    {formatted_ports},\n);"
        else:
            return "No module found."

