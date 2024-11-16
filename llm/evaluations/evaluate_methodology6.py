import sys
from pathlib import Path

# Add the project root to the PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.environment import Environment
from src.questasim import QuestaSim
from src.llama3_chat import LlamaChat
import argparse
from src.prompt_templates import m2_prompts, m3_prompt, design_prompt, error_prompt
from src.eval_runs_util import Record

if __name__=="__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--design', type=str, required=True, help="This is the path of the design directory that you would like to generate test benches for, not the path of the design file.")
    parser.add_argument('-g', '--generations', type=int, required=True)
    parser.add_argument('-c', '--compiler', type=str, required=True)
    args = parser.parse_args()

    environment = Environment(args.design)
    
    llama = LlamaChat(QuestaSim(args.compiler), temperature=0.3, top_p=0.7, max_new_tokens=8196, timeout_seconds=1200)

    record = Record(environment.design_name, "RUN")

    prompt1, prompt2 = m2_prompts(environment.design_specification, environment.module_header)
    print(prompt1)
    print(prompt2)

    temperature = 0.3
    top_p=0.7

    runs = args.generations

    cov = None

    for i in range(0,runs):
        
        # Reset the record for each run
        record.reset_run()

        # Run generations
        # Initialize conversation history with system message
        print(f"\n\nRun: {i}, Iteration: 0")
        conversation = [
            {"role": "system", "content": "You are a verification engineering assistant tasked with generating test benches that meet a coverage requirement of 100% statement coverage."}
        ]

        #-----------------------------------------------------------------------------------------------------------------
        # Beginning of conversation
        #-----------------------------------------------------------------------------------------------------------------
        conversation.append({"role":"user", "content":prompt1})

        # Generate the verification/test plan
        response, tokens_generated, generation_time = llama.generate_response(conversation_history=conversation)
        print(response)

        conversation.append({'role':"assistant", "content":response})
        conversation.append({"role":"user", "content":prompt2})

        # Generate the first test bench
        response, tokens_generated, generation_time = llama.generate_response(conversation_history=conversation)
        conversation.append({"role": "assistant", "content": response})
        response = LlamaChat.convert_json_response_to_dict(response)
        print(response)

        data_point = environment.dataset.get_data_point(environment.design_name)
        try:
            cov = llama.get_coverage(response[0]['test bench'], f'{args.design}/tb_llm_{environment.design_name}_{i}.v', data_point=data_point, storage=environment.store)
        except KeyError:
            continue

        record.update_dataframe(cov, temperature, top_p, i, 0, tokens_generated, generation_time)
        record.write_to_csv(f'./{environment.design_name}_methodology6.csv')

        #------------------------------------------------------------------------------------------------------------------
        # Iterate until the LLM generates a test bench that gives actual coverage
        # If the first test bench generated produced covergae, this will be skipped
        #------------------------------------------------------------------------------------------------------------------
        num_iter = 1
        while cov.total_coverage == 0 and num_iter < 12:

            print(f"\n\nRun: {i}, Iteration: {num_iter}")

            error = error_prompt(cov.error_code)
            print(error)

            conversation.append({"role":"user", "content":error})

            response, tokens_generated, generation_time = llama.generate_response(conversation_history=conversation)
            print(response)
            conversation.append({"role":"assistant", "content":response})
            response = LlamaChat.convert_json_response_to_dict(response)
            try:
                cov = llama.get_coverage(response[0]['test bench'], f'{args.design}/tb_llm_{environment.design_name}_{i}{num_iter}.v', data_point=data_point, storage=environment.store)
            except KeyError as e:
                print(f"KeyError: {e}")
                num_iter += 1
                continue

            record.update_dataframe(cov, temperature, top_p, i, num_iter, tokens_generated, generation_time)

            conversation = llama.limit_conversation(conversation)

            num_iter += 1

            record.write_to_csv(f'./{environment.design_name}_methodology6.csv')

        # If the script makes it here, cov should have information from a test bench with actual coverage, hence the assertion
        assert cov.total_coverage >= 0, "Unexpected state! Coverage should be greater than zero when it tries to pass the design to the LLM."

        # If it was able to generate a test bench with 100% coverage, it should move onto the next conversation
        if cov.total_coverage == 100:
            continue

        print(f"\n\nRun: {i}, Iteration: {num_iter}")

        whole_design_prompt = design_prompt(environment.top_design_file_path)
        print(whole_design_prompt)
        conversation.append({"role":"user", "content":whole_design_prompt})

        response, tokens_generated, generation_time = llama.generate_response(conversation_history=conversation)
        print(response)
        conversation.append({"role":"assistant", "content":response})
        response = LlamaChat.convert_json_response_to_dict(response)
        try:
            cov = llama.get_coverage(response[0]['test bench'], f'{args.design}/tb_llm_{environment.design_name}_{i}{num_iter}_from_design.v', data_point=data_point, storage=environment.store)
        except KeyError:
            print(f"KeyError: {e}")
            num_iter += 1
            continue

        record.update_dataframe(cov, temperature, top_p, i, 1, tokens_generated, generation_time)
        record.write_to_csv(f'./{environment.design_name}_methodology6.csv')

        llama.limit_conversation(conversation)

        #--------------------------------------------------------------------------------------------------------------------
        # Beginning of iteratively closing coverage
        # This will iterate until the end of the iterations or until it generates a test bench with no cover holes
        #--------------------------------------------------------------------------------------------------------------------
        num_iter += 1
        while record.max_cov != 100 and num_iter < 12:
            print(f"\n\nRun: {i}, Iteration: {num_iter}")

            prompt3 = m3_prompt(environment.top_design_file_path, cov)
            print(prompt3)

            conversation.append({"role":"user", "content":prompt3})

            response, tokens_generated, generation_time = llama.generate_response(conversation_history=conversation)
            print(response)
            conversation.append({"role": "assistant", "content": response})
            response = LlamaChat.convert_json_response_to_dict(response)

            try:
                cov = llama.get_coverage(response[0]['test bench'], f'{args.design}/tb_llm_{environment.design_name}_{i}{num_iter}.v', data_point=data_point, storage=environment.store)
            except KeyError:
                print(f"KeyError: {e}")
                num_iter += 1
                continue
            
            record.update_dataframe(cov, temperature, top_p, i, num_iter, tokens_generated, generation_time)

            # Limit conversation memory to about 8196 tokens (estimate based on token count)
            conversation = llama.limit_conversation(conversation)

            num_iter += 1

            record.write_to_csv(f'./{environment.design_name}_methodology6.csv')

        record.update_run_average_total_coverage(run_id=i)

        record.write_to_csv(f'./{environment.design_name}_methodology6.csv')
    
    record.write_to_csv(f'./{environment.design_name}_methodology6.csv')