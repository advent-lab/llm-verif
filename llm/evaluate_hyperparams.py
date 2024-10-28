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
from environment import Environment
from eval_runs_util import Record

if __name__=="__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-d1', '--design1', type=str, required=True, help="This is the path of the design directory that you would like to generate test benches for, not the path of the design file.")
    parser.add_argument('-d2', '--design2', type=str, required=True)
    parser.add_argument('-c', '--compiler', type=str, required=True)
    args = parser.parse_args()

    d1_environment = Environment(args.compiler, args.design1)
    d2_environment = Environment(args.compiler, args.design2)

    d1_record = Record(d1_environment.design_name)
    d2_record = Record(d1_environment.design_name)
    
    # Read the prompts
    d1_prompt = m1_prompt(d1_environment.design_specification, d1_environment.module_header)
    d2_prompt = m1_prompt(d2_environment.design_specification, d2_environment.module_header)

    for temperature in np.arange(0.1, 1.1, 0.1):
        for top_p in np.arange(0.1, 1.1, 0.1):
            
            for i in range(0,5):
                # Run generations
                # Initialize conversation history with system message
                print(f"\n\nRun {i}")
                conversation = [
                    {"role": "system", "content": "You are a verification engineering assistant tasked with generating test benches that meet a coverage requirement of 100% statement coverage."}
                ]
                conversation.append({"role":"user", "content":d1_prompt})

                response = chat.generate_response(conversation_history=conversation)
                response = chat.convert_json_response_to_dict(response)
                print(response)

                cov = chat.get_coverage(args.compiler, response[0]['test bench'], f'{args.design1}/tb_llm_{d1_environment.design_name}_{i}.v', data_point=d1_environment.dataset.get_data_point(d1_environment.design_name), storage=d1_environment.store)
                
                d1_record.update_dataframe(cov, temperature, top_p)

            for i in range(0,5):
                # Run generations
                # Initialize conversation history with system message
                print(f"\n\nRun {i}")
                conversation = [
                    {"role": "system", "content": "You are a verification engineering assistant tasked with generating test benches that meet a coverage requirement of 100% statement coverage."}
                ]
                conversation.append({"role":"user", "content":d2_prompt})

                response = chat.generate_response(conversation_history=conversation)
                response = chat.convert_json_response_to_dict(response)
                print(response)

                cov = chat.get_coverage(args.compiler, response[0]['test bench'], f'{args.design2}/tb_llm_{d2_environment.design_name}_{i}.v', data_point=d2_environment.dataset.get_data_point(d2_environment.design_name), storage=d2_environment.store)
                
                d2_record.update_dataframe(cov, temperature, top_p)

    # No need to recreate the DataFrame here, as it has been filled during the loop
    d1_record.update_average_total_coverage()
    
    d1_record.write_to_csv(f'./{d1_environment.design_module_name}_hyperparams_eval_results.csv')

    d2_record.update_average_total_coverage()
    
    d2_record.write_to_csv(f'./{d2_environment.design_module_name}_hyperparams_eval_results.csv')

            
