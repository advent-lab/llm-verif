import json
import sys
import re
import os
from SortFiles import RepoFiles
from FileRead import find_instance, find_all_regex

#TODO: Fix how functions are found with the regex pattern. Figure out how functions and classes work in sytemverilog


MODULE_PATTERN = re.compile(r'\bmodule\s+(\w+)')
INCLUDE_PATTERN = re.compile(r'`include\s+"([^"]+)"')
IMPORT_PATTERN = re.compile(r'import\s+([\w.]+)\s*::.*;')
PACKAGE_PATTERN = re.compile(r'\bpackage\s+(\w+)')
INTERFACE_PATTERN = re.compile(r'\binterface\s+(\w+)')
FUNCTION_PATTERN = re.compile(r'function\s+[\w\s\[\]:-]+\s+(\w+)\s*\(')
CLASS_PATTERN = re.compile(r'class')

class Node:
    def __init__(self, file_path):
        self.file = file_path
        self.next_nodes = []
        self.type = [] #This is used to identify where and how node is instantiated in other nodes

        self.includes = []

        self.pkg_def = []
        self.mod_def = []
        self.inter_def = []
        self.func_def = []

        self.pkg_inst = []
        self.mod_inst = []
        self.inter_inst = []
        self.func_inst = []


    '''
    Add next node to node
    '''
    def add_next(self, node):
        self.next_nodes.append(node)

    '''
    Set mod_def, inter_def, func_def, pkg_def, includes in node
    '''
    def set_keys(self, path):
        self.mod_def = find_all_regex(path, MODULE_PATTERN)
        self.includes = find_all_regex(path, INCLUDE_PATTERN)
        self.inter_def = find_all_regex(path, INTERFACE_PATTERN)
        self.func_def = find_all_regex(path, FUNCTION_PATTERN)
        self.pkg_def = find_all_regex(path, PACKAGE_PATTERN)
    
    '''
    Return DFS nodes visited
    '''
    def search_dep(self, node, visited=None):
        if visited is None:
            visited = set()
        for next in node.next_nodes:
            if next not in visited:
                visited.add(next)
                self.search_dep(next, visited)
            
        return visited

    '''
    Return nodes from dependent nodes
    '''
    def create_dep_list(self):
        dep_nodes = self.search_dep(self)
        dep_list = []
        for node in dep_nodes:
            if node not in dep_list:
                dep_list.append(node)
        return dep_list
    
    '''
    Convert node to dict
    '''
    def to_dict(self):
        return {
            "file": self.file,
            "type": self.type,
            "includes": self.includes,
            "package_definitions": self.pkg_def,
            "module_definitions": self.mod_def,
            "interface_definitions": self.inter_def,
            "function_definitions": self.func_def,
            "package_instances": self.pkg_inst,
            "module_instances": self.mod_inst,
            "interface_instances": self.inter_inst,
            "function_instances": self.func_inst,
            "file_dep": [node.file for node in self.next_nodes]
        }

class Graph:
    def __init__(self):
        self.files = []
        self.nodes = []
        self.top_nodes = []

    '''
    Fill list with new nodes from repo files
    ''' 
    def fill_nodes(self, repo_files):
        self.files = repo_files
        for path in repo_files:
            new_node = Node(path)
            new_node.set_keys(path)
            self.nodes.append(new_node)

    '''
    Find whenever a definition from any node file
    is instatiated in the base file
    '''
    def fill_instances(self, def_attr, def_inst):
        for base in self.nodes:
            for node in self.nodes:
                if node!= base:
                    for name in getattr(node, def_attr):
                        if find_instance(base.file, name):
                            getattr(base, def_inst).append(name)

    '''
    Fill each nodes instances data
    '''                
    def fill_all_instances(self):
        self.fill_instances('mod_def', 'mod_inst')
        self.fill_instances('inter_def', 'inter_inst')
        self.fill_instances('func_def', 'func_inst')
        self.fill_instances('pkg_def', 'pkg_inst')
            
    '''
    Return list of module instances from all files found in repo
    '''
    def create_instance_list(self):
        instance_list = []
        for node in self.nodes:
            for inst in node.mod_inst:
                if inst not in instance_list:
                    instance_list.extend(node.mod_inst)

        return instance_list
    
    '''
    Fill each nodes next with a node object from their dependencies
    '''
    def fill_edges(self, inst_attr, def_attr, type):
        for base in self.nodes:
            for depend in getattr(base, inst_attr):
                for node in self.nodes:
                    if depend in getattr(node, def_attr) and node not in base.next_nodes:
                        node.type.append({'type':type, 'location': os.path.basename(base.file)})
                        base.add_next(node)

    def fill_all_edges(self):
        self.fill_edges('mod_inst', 'mod_def', 'module')
        self.fill_edges('inter_inst', 'inter_def', 'interface')
        self.fill_edges('func_inst', 'func_def', 'function')
        self.fill_edges('pkg_inst', 'pkg_def', 'package')
        self.fill_edges('includes', 'file', 'include')

    '''
    Find file with top module not used in other repo files
    '''
    def find_top_nodes(self):
        list = self.create_instance_list()
        for base in self.nodes:
            if base.mod_def is None:
                continue
            for module in base.mod_def:
                if module not in list and base not in self.top_nodes:
                    self.top_nodes.append(base)
                            
    '''
    Print graph in json format
    '''
    def to_json(self):
        dict_list = self.to_dict()

        print([node.file for node in self.top_nodes])

        with open("GraphStructure.json", 'w') as file:
            json.dump(dict_list, file, indent=4)


    '''
    Convert graph to dict
    '''
    def to_dict(self):
        dict_list = []
        for node in self.nodes:
            dict_list.append(node.to_dict())
        
        return dict_list

def main():
    if len(sys.argv) == 2:
        root = sys.argv[1]

        files = RepoFiles(root)
        files.sort_files()

        graph = Graph()
        graph.fill_nodes(files.hdl_set)
        graph.fill_all_instances()
        graph.fill_all_edges()
        graph.find_top_nodes()
        graph.to_json()

    else:
        print(f"Usage: {sys.argv[0]} <repos path>")
        print(f"Expected: 1 arguments, got {len(sys.argv)-1}")
        sys.exit(1)
if __name__ == "__main__":
    main()