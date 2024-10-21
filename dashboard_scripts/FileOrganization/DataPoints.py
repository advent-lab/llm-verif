import json
import os
import sys
from GraphStructure import Graph
from SortFiles import RepoFiles

'''
Print data entries in json format
'''
def to_json(list, path):
    with open(path, 'w') as f:
        json.dump(list, f, indent=4)

'''
Definition of a data point
One verif file with all file dependencies
'''
class DataPoint:
    def __init__(self, repo_name):
        self.data = {
            repo_name:{
                "verif": [],
                "verif_context": [],
                "design": [],
                "design_context": [],
                "include": [],
                "spec": [],
                "read_me": [],
                "license": [],
                "makefile": [],
                "tags": [],
                "repo_link": ""
            }
        }
    def to_dict(self):
        return self.data
    
class RepoDataPoints:
    def __init__(self, path, graph, files):
        self.path = path[:-1] if path[-1] == '/' else path
        self.graph = graph
        self.files = files        
        self.data_points = []

    #TODO: May need to change the dictionary structure to reflect how data point is structured
    #The structure of verif, verif_context, design, design_context may be too simplistic
    #Fix terrenary expressions, hard to read
    def set_data_points(self):

        # Create a data point for every top node
        for top_node in self.graph.top_nodes:
            visited = set()
            project_name = os.path.basename(self.path)
            data_point = DataPoint(project_name)

            # Populate initial data point fields
            data_point.data[project_name]["verif"].append(top_node.file)
            data_point.data[project_name]["spec"].extend(self.files.spec_set)
            data_point.data[project_name]["read_me"].extend(self.files.readme_set)
            data_point.data[project_name]["license"].extend(self.files.license_set)
            data_point.data[project_name]["makefile"].extend(self.files.makefile_set)

            # Common processing for each node type
            for node in top_node.next_nodes:
                base_file = os.path.basename(top_node.file)

                # Check how node is used in top node
                for node_type in node.type:
                    target = 'include' if node_type['type'] == 'include' else 'verif_context' if node_type['type'] != "module" else "design"
                    if node_type["location"] == base_file and node.file not in visited:
                        # rel_path = os.path.relpath(node.file, self.path)
                        data_point.data[project_name][target].append(node.file)
                        visited.add(node.file)

                        # Process child dependencies
                        for child_node in node.create_dep_list():
                            target_context = 'include' if node_type['type'] == 'include' else 'design_context' if node_type['type'] == "module" else 'verif_context'
                            if child_node.file not in visited:
                                # rel_path = os.path.relpath(child_node.file, self.path)
                                data_point.data[project_name][target_context].append(child_node.file)
                                visited.add(child_node.file)

            if data_point.data[project_name]["verif_context"] or data_point.data[project_name]["design"] or data_point.data[project_name]["design_context"]:
                self.data_points.append(data_point)

    def to_dict(self):
        list = []
        for data in self.data_points:
            list.append(data.to_dict())
        return list
           
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
        list = []

        data = RepoDataPoints(root, graph, files)
        data.set_data_points()
        list.extend(data.to_dict())

        to_json(list, 'DataPoint.json')
        print("Done creating data points for " + data.path)

    else:
        print(f"Expected: 1 arguments, got {len(sys.argv)-1}")
        sys.exit(1)
        
if __name__ == "__main__":
    main()
