import llama3_chat as chat
from storage import FileStore
import os
import argparse
import pandas as pd
import numpy as np
from evaluation import pass_at_k
from prompt_templates import m1_prompt
from pathlib import Path
from dashboard import Dataset

if __name__=="__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--design', type=str, required=True, help="This is the path of the design directory that you would like to generate test benches for, not the path of the design file.")
    parser.add_argument('-g', '--generations', type=int, required=True)
    parser.add_argument('-c', '--compiler', type=str, required=True)
    args = parser.parse_args()

    df = pd.DataFrame(columns=[
        "design",
        "temperature", 
        "top_p", 
        "pass rate",
        "pass@1",
        "pass@5",
        "pass@8",
        "pass@10",
        "compile fails",
        "sim fails",
        "timeout fails",
        "report fails",
        "decode fails",
        "compile fail rate",
        "sim fail rate",
        "timeout fail rate",
        "report fail rate",
        "decode fail rate",
        "max total coverage",
        "average total coverage",
    ])

    design_dir = args.design
    design_name = os.path.split(design_dir)[1]
    design_dir_path = Path(args.design)
    dashboard_path = f'{str(design_dir_path.parents[1])}/dashboard.json'

    dataset = Dataset(dashboard_path)
    
    # Create the prompt
    # Read the specification file
    # TODO: Add support for PDF specification files/documentation
    design_specification_path = dataset.get_design_spec(design_name)
    design_specification = ''
    if not design_specification_path:
        print("Error: No design specification avaliable for this design")
        exit()
    elif isinstance(design_specification_path, list):
        # Here we assume the top item in the spec tag is the correct specification
        # This should not really happen because there should only be one specification file in the spec tag
        with open(design_specification_path[0], 'r') as spec:
            design_specification = spec.read()
    else:
        with open(design_specification_path, 'r') as spec:
            design_specification = spec.read()

    top_design_file_path = dataset.get_design(design_name)
    module_header = ''
    if not top_design_file_path:
        print("Error: No design file(s) avaliable for this design")
        exit()
    elif isinstance(top_design_file_path, list):
        # Here we assume the top item in the spec tag is the correct specification
        # This should not really happen because there should only be one specification file in the spec tag
        top_design_file_path = top_design_file_path[0]
        module_header = chat.extract_verilog_module_header(top_design_file_path)
    else:
        module_header = chat.extract_verilog_module_header(top_design_file_path)

    prompt = m1_prompt(design_specification, module_header)
    print(prompt)

    design_module_name = chat.get_design_name(top_design_file_path)

    # Create a directory to store generations
    store = FileStore('./generations')
    chat.load_model()

    temperature = 0.6
    top_p=0.9

    total_pass = 0
    total_fail = 0
    num_compile_fail = 0 # A high number of compile failures means its is generating too many test benches that cannot compile
    num_sim_fail = 0 # A high number fo sim failures means its generating too many test benches that cannot simulate
    num_timeout_fail = 0 # A high number of timeout failures means you might want to increase the timeout
    num_report_fail = 0 # A high number of report failures might imply some other structural error
    num_decode_fail = 0 # A high number of decode failures means the llm is generating unfinished test benches

    max_cov = 0
    sum_cov_of_success = 0
    avg_total_coverage = 0

    runs = args.generations

    for i in range(0,runs):
        # Run generations
        # Initialize conversation history with system message
        print(f"\n\nRun {i}")
        conversation = [
            {"role": "system", "content": "You are a verification engineering assistant tasked with generating test benches that meet a coverage requirement of 100% statement coverage."}
        ]
        conversation.append({"role":"user", "content":prompt})

        response = chat.generate_response(conversation_history=conversation)
        response = chat.convert_json_response_to_dict(response)
        print(response)

        cov = chat.get_coverage(args.compiler, response[0]['test bench'], f'{args.design}/tb_llm_{design_name}_{i}.v', data_point=dataset.get_data_point(design_name), storage=store)
        if cov.success:
            print(f"Passed!\n{cov.error_message}")
            total_pass = total_pass + 1
            sum_cov_of_success = sum_cov_of_success + int(cov.total_coverage)
            if int(cov.total_coverage) > max_cov:
                max_cov = int(cov.total_coverage)
        else:
            print(f"Failed!\n{cov.error_message}")
            total_fail = total_fail + 1
            if cov.error_code == 1:
                num_compile_fail = num_compile_fail + 1
            elif cov.error_code == 2:
                num_sim_fail = num_sim_fail + 1
            elif cov.error_code == 3:
                num_timeout_fail = num_timeout_fail + 1
            elif cov.error_code == 4:
                num_report_fail = num_report_fail + 1
            else:
                num_decode_fail = num_decode_fail + 1

        df = pd.concat([df, pd.DataFrame([{
            "design": design_name,
            "temperature": temperature, 
            "top_p": top_p, 
            "pass rate": total_pass / (total_pass + total_fail) if (total_pass + total_fail) != 0 else 0,
            "pass@1": pass_at_k((total_pass + total_fail), total_pass, 1),
            "pass@5": pass_at_k((total_pass + total_fail), total_pass, 5),
            "pass@8": pass_at_k((total_pass + total_fail), total_pass, 10),
            "pass@10": pass_at_k((total_pass + total_fail), total_pass, 25),
            "compile fails": num_compile_fail,
            "sim fails": num_sim_fail,
            "timeout fails": num_timeout_fail,
            "report fails": num_report_fail,
            "decode fails": num_decode_fail,
            "compile fail rate": num_compile_fail / (total_pass + total_fail) if (total_pass + total_fail) != 0 else 0,
            "sim fail rate": num_sim_fail / (total_pass + total_fail) if (total_pass + total_fail) != 0 else 0,
            "timeout fail rate": num_timeout_fail / (total_pass + total_fail) if (total_pass + total_fail) != 0 else 0,
            "report fail rate": num_report_fail / (total_pass + total_fail) if (total_pass + total_fail) != 0 else 0,
            "decode fail rate": num_decode_fail / (total_fail + total_pass) if (total_pass + total_fail) != 0 else 0,
            "max total coverage": max_cov
        }])], ignore_index=True)  # Appending to df
        print(df)

    # No need to recreate the DataFrame here, as it has been filled during the loop
    df["average total coverage"] = sum_cov_of_success / total_pass if total_pass != 0 else 0
    
    df.to_csv('methodology1.csv', index=False)