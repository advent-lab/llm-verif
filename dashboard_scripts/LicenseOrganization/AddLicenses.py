import json
import os

LICENSE = {"LICENSE", "License", "license"}

root = "/mnt/vault0/asbabbit/ml_for_hdl/llm_verif_dataset/data_points"
dashboard = "/mnt/vault0/asbabbit/ml_for_hdl/llm_verif_dataset/dashboard.json"

def write_json(file, license, dp_name):
    try:

        with open(file, "r") as j:
            data = json.load(j)

        data[dp_name]["license"] = license


        with open(file, 'w') as j:
            json.dump(data, j, indent=4)

    except KeyError as e:
        print(f"datapoint {dp_name} not in dashboard")

def helper(path):
    if os.path.isdir(path):
        for item in os.listdir(path):
            item_path = os.path.join(path,item)

            if os.path.isdir(item_path) and '.git' not in item_path:
                helper(item_path)
            
            elif os.path.isfile(item_path):
                file = os.path.basename(item_path)
                license = os.path.splitext(file)[0]
                if license in LICENSE:
                    return item_path

            else:
                return "No license found"

for name in os.listdir(root):
   path = os.path.join(root, name)
   license = helper(path)
   write_json(dashboard, license, name)
