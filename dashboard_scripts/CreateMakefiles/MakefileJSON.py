import os
import json

# Makefile blueprint
MAKEFILE_TEMPLATE = """QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
BASE_DIR ?= {base_dir}
PROJECT_DIR ?= $(BASE_DIR)/{project_dir}
PROJECT_FILES ?= {project_files}

all: worklib compile sim

worklib:
\techo "creating worklib"
\t$(QUESTA_ROOT)/vlib work

compile:
\techo "compiling design files"
\t$(QUESTA_ROOT)/vlog -cover bcs{include_dir} $(PROJECT_FILES)

sim: 
\techo "simulating test bench and generating .ucdb coverage report"
\t$(QUESTA_ROOT)/vsim work.{top_verif_file} -c -coverage -do "coverage save -onexit {top_verif_file}.ucdb; run -all; exit"

clean: 
\trm -rf work transcript
"""

def relative_path(path, name):
    path = path.split(os.sep)
    
    # Find the index of the directory_name
    if name in path:
        index = path.index(name)
        # Join the parts after the directory_name
        return os.sep.join(path[index + 1:])

def generate_makefile_from_json(json_file_path, base_dir):
    with open(json_file_path, 'r') as file:
        data = json.load(file)

    for project, categories in data.items():
        project_dir = os.path.join(base_dir, project)

        project_files = ""
        include_dir = ""

        # Determine the top-level verification file (first file in 'verif' category, if exists)
        top_file_path = os.path.basename(categories.get('verif', [""])[0])
        top_verif_file = os.path.splitext(top_file_path)[0]
        
        # Gather all files from categories
        for category, file_list in categories.items():
            if file_list:
                if category in ["verif","verif_context","design","design_context"]:
                    # Create string of project files
                    for file in file_list:
                        rel_path = relative_path(file, project)
                        project_files = project_files + f" $(PROJECT_DIR)/{rel_path}"
                # Assuming there is only one includes folder
                if category == "include" and os.path.dirname(file) not in include_dir:
                    include_dir = f' +incdir+{os.path.dirname(file)}'
            
        # Fill in the Makefile template
        makefile_content = MAKEFILE_TEMPLATE.format(
            base_dir=base_dir,
            project_dir=project_dir,
            project_files=project_files,
            include_dir=include_dir,
            top_verif_file=top_verif_file,
        )
        
        # Write the Makefile to the destination path
        makefile_path = os.path.join(project_dir, "questa/Makefile")
        os.makedirs(base_dir, exist_ok=True)
        with open(makefile_path, 'w') as makefile:
            makefile.write(makefile_content)
        
        print(f'Makefile created at {makefile_path}')
        
# Define your JSON file path, destination base path, and Questa root
json_file_path = '/mnt/vault0/asbabbit/ml_for_hdl/llm_verif_dataset/dashboard_scripts/DataPoint.json'
base_dir = '/mnt/vault0/asbabbit/ml_for_hdl/llm_verif_dataset/data_points'

# Generate the Makefile
generate_makefile_from_json(json_file_path, base_dir)