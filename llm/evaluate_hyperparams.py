import llama3_chat as chat
import argparse
from prompt_templates import m1_prompt
from environment import Environment
from eval_runs_util import Record
import numpy as np
import torch

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-d1', '--design1', type=str, required=True, help="Path to the design directory for generating test benches.")
    parser.add_argument('-d2', '--design2', type=str, required=True)
    parser.add_argument('-c', '--compiler', type=str, required=True)
    args = parser.parse_args()

    d1_environment = Environment(args.compiler, args.design1)
    d2_environment = Environment(args.compiler, args.design2)

    d1_record = Record(d1_environment.design_name)
    d2_record = Record(d2_environment.design_name)

    d1_prompt = m1_prompt(d1_environment.design_specification, d1_environment.module_header)
    d2_prompt = m1_prompt(d2_environment.design_specification, d2_environment.module_header)

    for temperature in np.arange(0.1, 1.1, 0.1):
        for top_p in np.arange(0.1, 1.1, 0.1):
            for i in range(5):  # Loop over response generation count per design

                # Run generation for design1
                print(f"\n\nRun {i} for Design1 at temp {temperature}, top_p {top_p}")
                conversation = [
                    {"role": "system", "content": "You are a verification engineering assistant tasked with generating test benches that meet a coverage requirement of 100% statement coverage."},
                    {"role": "user", "content": d1_prompt}
                ]

                response = chat.generate_response(conversation_history=conversation, max_new_tokens=4096, temperature=temperature, top_p=top_p)
                response = chat.convert_json_response_to_dict(response)
                
                cov = chat.get_coverage(args.compiler, response[0]['test bench'], f'{args.design1}/tb_llm_{d1_environment.design_name}_{i}.v', data_point=d1_environment.dataset.get_data_point(d1_environment.design_name), storage=d1_environment.store)
                
                d1_record.update_dataframe(cov, temperature, top_p)

                torch.cuda.empty_cache()  # Clear cache between designs

                # Run generation for design2
                print(f"\n\nRun {i} for Design2 at temp {temperature}, top_p {top_p}")
                conversation = [
                    {"role": "system", "content": "You are a verification engineering assistant tasked with generating test benches that meet a coverage requirement of 100% statement coverage."},
                    {"role": "user", "content": d2_prompt}
                ]

                response = chat.generate_response(conversation_history=conversation, max_new_tokens=4096, temperature=temperature, top_p=top_p)
                response = chat.convert_json_response_to_dict(response)
                
                cov = chat.get_coverage(args.compiler, response[0]['test bench'], f'{args.design2}/tb_llm_{d2_environment.design_name}_{i}.v', data_point=d2_environment.dataset.get_data_point(d2_environment.design_name), storage=d2_environment.store)
                
                d2_record.update_dataframe(cov, temperature, top_p)

                torch.cuda.empty_cache()  # Free memory after each response generation

            # Intermediate checkpoint: Save results and clear GPU memory after every set of temperature and top_p
            d1_record.write_to_csv(f'./{d1_environment.design_module_name}_hyperparams_eval_results.csv')
            d2_record.write_to_csv(f'./{d2_environment.design_module_name}_hyperparams_eval_results.csv')
            torch.cuda.empty_cache()

    # Final save
    d1_record.update_average_total_coverage()
    d1_record.write_to_csv(f'./{d1_environment.design_module_name}_final_hyperparams_eval_results.csv')

    d2_record.update_average_total_coverage()
    d2_record.write_to_csv(f'./{d2_environment.design_module_name}_final_hyperparams_eval_results.csv')


            
