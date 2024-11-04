import json
import pprint

root = "/mnt/vault0/asbabbit/ml_for_hdl/llm_verif_dataset/data_points"
dashboard = "/mnt/vault0/asbabbit/ml_for_hdl/llm_verif_dataset/dashboard.json"

def print_amount_license(file):
    data = read_dashboard(file)
    licenses = {
        "MIT License": 0,
        "3-Clause BSD License": 0,
        "Apache License": 0,
        "GNU Lesser General Public License (LGPL)": 0,
        "Other license type": 0

    }
    
    for data_point in data:
        for tag in data[data_point].get("tags", []):
            match tag:
                case "MIT License":
                    licenses["MIT License"] += 1
                case "3-Clause BSD License":
                    licenses["3-Clause BSD License"] += 1
                case "Apache License":
                    licenses["Apache License"] += 1
                case "GNU Lesser General Public License (LGPL)":
                    licenses["GNU Lesser General Public License (LGPL)"] += 1
                case "Other license type":
                    licenses["Other license type"] += 1
    
    pprint.pprint(licenses)

def write_dashboard(file, data, name, license_type):
    try:
        if license_type is not None and license_type not in data[name]["tags"]:
            data[name]["tags"].append(license_type)
        with open(file, 'w') as j:
            json.dump(data, j, indent=4)

    except KeyError as e:
        print(f"{data_point} not listed on dashboard")

def read_dashboard(file):
    with open(file, "r") as j:
            data = json.load(j)

    return data

def read_license(relative_path, new_root, data_point):
    try:
        actual_path = relative_path.replace("$(BASE_DIR)", new_root)
        if not actual_path:
            print(f"no license exists for {data_point}")
            return None
                  
        with open(actual_path, "r") as j:
            contents = j.read()

        return contents
    
    except KeyError as e:
        print(f"no license exists or {data_point} not listed on dashboard")

 
def identify_license(license_text):
    # Define keywords for different licenses
    licenses = {
        "MIT License": [
            "permission is hereby granted",
            "copy, modify, merge, publish, distribute",
            "MIT L"
        ],
        "3-Clause BSD License": [
            "Redistribution and use in source and binary forms",
            "with or without modification",
            "no endorsement"
        ],
        "Apache License": [
            "grants you a worldwide, royalty-free",
            "license to use, reproduce, modify",
            "Apache"
        ],
        "GNU General Public License (GPL)": [
            "GNU General Public License",
            "this program is free software",
            "you can redistribute it and/or modify it"
        ],
        "GNU Lesser General Public License (LGPL)": [
            "GNU Lesser General"
        ]
    }

    if license_text is not None or "":

        for license_type, keywords in licenses.items():
            if any(keyword in license_text for keyword in keywords):
                return license_type

        return "Other license type"
    return None

data = read_dashboard(dashboard)
for data_point in data:
    license_type = identify_license(read_license(data[data_point]["license"], root, data_point))
    write_dashboard(dashboard, data, data_point, license_type)

print_amount_license(dashboard)