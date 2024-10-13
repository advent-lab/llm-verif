import os
import shutil
import json
import sys

def create_directories_and_copy_files(base_dir, data):
    for project in data:
        for folder, contents in project.items():
            print(f"Processing project: {folder}")
            
            # Create the directory for the project
            project_dir = os.path.join(base_dir, folder)
            if not os.path.exists(project_dir):
                os.makedirs(project_dir)

            # Create the directory for the questa simulation    
            questa_dir = os.path.join(project_dir, "questa")
            if not os.path.exists(questa_dir):
                os.makedirs(questa_dir)
            
            # Process each category within the project
            for category, files in contents.items():
                print(f"  Processing category: {category}")
                category_dir = os.path.join(project_dir, category)
                if not os.path.exists(category_dir):
                    os.makedirs(category_dir)

                for file_path in files:
                    if os.path.exists(file_path):
                        file_name = os.path.basename(file_path)
                        destination = os.path.join(category_dir, file_name)
                        shutil.copy(file_path, destination)
                        print(f"    Copied '{file_path}' to '{destination}'")
                    else:
                        print(f"    File '{file_path}' does not exist. Skipping...")

def main():
    json_file = "/mnt/vault0/asbabbit/ml_for_hdl/scripts/GHScraper/FileOrganization/Test.json"
    
    with open(json_file, 'r') as file:
        data = json.load(file)
    
    base_dir = "/mnt/vault0/asbabbit/ml_for_hdl/llm_"  # Base directory to start creating folders and copying files

    create_directories_and_copy_files(base_dir, data)

if __name__ == "__main__":
    main()
