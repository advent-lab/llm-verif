import json
import sys

with open("/mnt/vault0/asbabbit/ml_for_hdl/llm_verif_dataset/dashboard.json", "r") as file:
    data = json.load(file)

def find_empty_keys(key):
    for entry, details in data.items():
        if key in details and not details[key]:  # Check if the value is empty
            print(f"Entry '{entry}' has an empty key: '{key}'")
            i = i + 1
    print(i)

find_empty_keys(sys.argv[1])