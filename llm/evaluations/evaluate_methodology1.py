import sys
from pathlib import Path

# Add the project root to the PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parents[1]))

import src.llama3_chat as chat
import argparse
from src.prompt_templates import m1_prompt
from src.environment import Environment
from src.eval_runs_util import Record

if __name__=="__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--design', type=str, required=True, help="This is the path of the design directory that you would like to generate test benches for, not the path of the design file.")
    parser.add_argument('-g', '--generations', type=int, required=True)
    parser.add_argument('-c', '--compiler', type=str, required=True)
    args = parser.parse_args()

    environment = Environment(args.compiler, args.design)

    record = Record(environment.design_name)

    prompt = m1_prompt(environment.design_specification, environment.module_header)
    print(prompt)

    temperature = 0.3
    top_p = 0.7

    runs = args.generations

    for i in range(0,runs):

        record.reset_run()

        # Run generations
        # Initialize conversation history with system message
        print(f"\n\nRun {i}")
        conversation = [
            {"role": "system", "content": "You are a verification engineering assistant tasked with generating test benches that meet a coverage requirement of 100% statement coverage."}
        ]
        conversation.append({"role":"user", "content":prompt})

        response, tokens_generated, generation_time = chat.generate_response(conversation_history=conversation)
        conversation.append({"role": "assistant", "content": response})
        response = chat.convert_json_response_to_dict(response)
        print(response)

        cov = chat.get_coverage(environment, response[0]['test bench'], f'{args.design}/tb_llm_{environment.design_name}_{i}.v', data_point=environment.dataset.get_data_point(environment.design_name), storage=environment.store)
        
        record.update_dataframe(cov, temperature, top_p, i, 0, tokens_generated, generation_time)

        record.write_to_csv(f'./{environment.design_name}_methodology1.csv')

    # No need to recreate the DataFrame here, as it has been filled during the loop
    record.update_all_average_total_coverage()
    
    record.write_to_csv(f'./{environment.design_name}_methodology1.csv')