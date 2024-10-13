import os
import shutil
import json
import sys

def copy_files_from_json(json_file_path, dest_base_path):
    with open(json_file_path, 'r') as file:
        data = json.load(file)

    for project, categories in data.items():
        print(f'Processing project: {project}')
        
        for category, file_list in categories.items():
            if file_list:  # Only process if there are files in the list
                print(f'Processing category: {category}')
                
                for src_file_path in file_list:
                    # Extract the project directory name from the source path
                    project_dir = src_file_path.split('/')[6] 
                    # Extract the relative path of the file within the project directory
                    relative_path = os.path.relpath(src_file_path, start=f'/mnt/vault0/asbabbit/ml_for_hdl/compiled_repos/{project_dir}')
                    
                    # Define the destination directory based on the base path and relative path
                    dest_file_path = os.path.join(dest_base_path, relative_path)
                    dest_dir = os.path.dirname(dest_file_path)  # Get the directory of the destination file
                    
                    # Create the necessary directories
                    os.makedirs(dest_dir, exist_ok=True)
                    
                    # Copy the file to the destination
                    shutil.copy(src_file_path, dest_file_path)
                    
                    print(f'Copied {src_file_path} to {dest_file_path}')

def main():
    json_file = "/mnt/vault0/asbabbit/ml_for_hdl/scripts/GHScraper/FileOrganization/Test.json"
    base_dir = "/mnt/vault0/asbabbit/ml_for_hdl/data_points"  # Base directory to start creating folders and copying files

    copy_files_from_json(json_file, base_dir)

if __name__ == "__main__":
    main()
