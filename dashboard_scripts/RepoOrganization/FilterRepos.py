import os
import shutil
import sys

# Define the folder names for each category
VERIF = ["bench", "tb", "testbench", "verif", "example_tb", "test", "tests", "dv"]
DESIGN = ["rtl", "hdl", "verilog", "ip", "core"]
SPEC = ["doc", "docs", "spec", "documentation", "specification"]

def check_folders(project_dir):
    found_verif = False
    found_design = False
    found_spec = False

    for root, dirs, _ in os.walk(project_dir):
        # Check if any of the directories match the required names
        if not found_verif:
            found_verif = any(folder in VERIF for folder in dirs)
        if not found_design:
            found_design = any(folder in DESIGN for folder in dirs)
        if not found_spec:
            found_spec = any(folder in SPEC for folder in dirs)
        
        # If all categories are found, no need to continue searching
        if found_verif and found_design and found_spec:
            return True

    return found_verif and found_design and found_spec

def copy_project_if_valid(source_dir, destination_dir):
    for project in os.listdir(source_dir):
        project_path = os.path.join(source_dir, project)
        destination_project_path = os.path.join(destination_dir, project)

        # Check if the project directory already exists in the destination
        if os.path.isdir(project_path) and check_folders(project_path):
            if not os.path.exists(destination_project_path):
                try:
                    shutil.copytree(project_path, destination_project_path)
                    print(f"Copied project: {project_path} to {destination_project_path}")
                except shutil.Error as e:
                    print(f"Error copying {project_path}: {e}")
                except OSError as e:
                    print(f"OS error: {e}")
            else:
                print(f"Project {project_path} already exists in the destination. Skipping copy.")

def main():
    if len(sys.argv) == 3:
        root = sys.argv[1]
        new_root = sys.argv[2]

        copy_project_if_valid(root, new_root)
    else:
        print(f"Usage: {sys.argv[0]} <repos path> <copy_to path>")
        print(f"Expected: 2 arguments, got {len(sys.argv)-1}")
        return
            
    print(f"Repos copied")

if __name__ == "__main__":
    main()
