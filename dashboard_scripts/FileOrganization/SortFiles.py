import os
import sys

# Common names for meta data
README = {"README.md","ReadMe.md", "readme.md", "README.txt","ReadMe.txt", "readme.txt"}
MAKEFILE = "Makefile"
LICENSE = {"LICENSE", "License", "license"}

# File type mappings
FILE_TYPES = {
    'hdl': {".sv", ".v", ".svh", ".vh"},
    'spec': {".pdf", ".doc", ".txt", ".md"},
    'meta': {"", ".md"}
}

class RepoFiles:
    def __init__(self, root):
        self.root = root
        self.hdl_set = set()
        self.spec_set = set()
        self.readme_set = set()
        self.makefile_set = set()
        self.license_set = set()
    
    '''
    Sort files into sets of files of same type
    '''
    def sort_files(self):
        self._sort_files(self.root)

    '''
    Helper function
    '''
    def _sort_files(self, path):
        if os.path.isdir(path):
            for item in os.listdir(path):
                item_path = os.path.join(path, item)

                if os.path.isdir(item_path) and '.git' not in item_path: 
                    self._sort_files(item_path)

                elif os.path.isfile(item_path):
                    self._add_to_set(item_path)

    '''
    Add file to corresponding files set
    '''
    def _add_to_set(self, item_path):
        file = os.path.basename(item_path)
        name = os.path.splitext(file)
        extension = os.path.splitext(item_path)[1]

        if extension in FILE_TYPES['hdl']:
            self.hdl_set.add(item_path)
        elif extension in FILE_TYPES['spec'] and name not in LICENSE:
            self.spec_set.add(item_path)
        elif extension in FILE_TYPES['meta']:
            filename = os.path.basename(item_path)
            if filename in README:
                self.readme_set.add(item_path)
            elif filename in LICENSE:
                self.license_set.add(item_path)
            elif filename in MAKEFILE:
                self.makefile_set.add(item_path)
