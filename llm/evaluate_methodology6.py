import llama3_chat as chat
import argparse
from prompt_templates import m2_prompts, m3_prompt, design_prompt
from environment import Environment
from eval_runs_util import Record

if __name__=="__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--design', type=str, required=True, help="This is the path of the design directory that you would like to generate test benches for, not the path of the design file.")
    parser.add_argument('-g', '--generations', type=int, required=True)
    parser.add_argument('-c', '--compiler', type=str, required=True)
    args = parser.parse_args()

    environment = Environment(args.compiler, args.design)

    record = Record(environment.design_name, "RUN")

    prompt1, prompt2 = m2_prompts(environment.design_specification, environment.module_header)
    print(prompt1)
    print(prompt2)

    temperature = 0.3
    top_p=0.7

    runs = args.generations

    for i in range(0,runs):

        record.reset_run()

        # Run generations
        # Initialize conversation history with system message
        print(f"\n\nRun: {i}, Iteration: 0")
        conversation = [
            {"role": "system", "content": "You are a verification engineering assistant tasked with generating test benches that meet a coverage requirement of 100% statement coverage."}
        ]
        conversation.append({"role":"user", "content":prompt1})

        response, tokens_generated, generation_time = chat.generate_response(conversation_history=conversation)
        print(response)

        conversation.append({'role':"assistant", "content":response})
        conversation.append({"role":"user", "content":prompt2})

        response, tokens_generated, generation_time = chat.generate_response(conversation_history=conversation)
        conversation.append({"role": "assistant", "content": response})
        response = chat.convert_json_response_to_dict(response)
        print(response)

        data_point = environment.dataset.get_data_point(environment.design_name)
        try:
            cov = chat.get_coverage(environment, response[0]['test bench'], f'{args.design}/tb_llm_{environment.design_name}_{i}.v', data_point=data_point, storage=environment.store)
        except KeyError:
            continue

        record.update_dataframe(cov, temperature, top_p, i, 0, tokens_generated, generation_time)

        print(f"\n\nRun: {i}, Iteration: 1")

        whole_design_prompt = design_prompt(environment.top_design_file_path)
        conversation.append({"role":"user", "content":whole_design_prompt})

        response, tokens_generated, generation_time = chat.generate_response(conversation_history=conversation)
        conversation.append({"role":"assistant", "content":response})
        response = chat.convert_json_response_to_dict(response)
        try:
            cov = chat.get_coverage(environment, response[0]['test bench'], f'{args.design}/tb_llm_{environment.design_name}_{i}_from_design.v', data_point=data_point, storage=environment.store)
        except KeyError:
            continue

        record.update_dataframe(cov, temperature, top_p, i, 1, tokens_generated, generation_time)

        num_iter = 2
        while num_iter < 12:

            print(f"\n\nRun: {i}, Iteration: {num_iter}")

            prompt3 = m3_prompt(environment.top_design_file_path, cov)
            print(prompt3)

            conversation.append({"role":"user", "content":prompt3})

            response, tokens_generated, generation_time = chat.generate_response(conversation_history=conversation)
            conversation.append({"role": "assistant", "content": response})
            response = chat.convert_json_response_to_dict(response)
            print(response)

            try:
                cov = chat.get_coverage(environment, response[0]['test bench'], f'{args.design}/tb_llm_{environment.design_name}_{i}{num_iter}.v', data_point=data_point, storage=environment.store)
            except KeyError:
                continue
            record.update_dataframe(cov, temperature, top_p, i, num_iter, tokens_generated, generation_time)

            # Limit conversation memory to about 8196 tokens (estimate based on token count)
            current_token_count = sum(len(environment.tokenizer.encode(msg["content"])) for msg in conversation)
            max_token_count = 128000 - 8196
            while current_token_count > max_token_count:
                # Remove the oldest messages to maintain memory size
                conversation.pop(1)  # Assuming the first message is the system prompt, so we pop the second one
                current_token_count = sum(len(self.tokenizer.encode(msg["content"])) for msg in conversation)

            num_iter += 1

            record.write_to_csv(f'./{environment.design_name}_methodology6.csv')

        record.update_run_average_total_coverage(run_id=i)

        record.write_to_csv(f'./{environment.design_name}_methodology6.csv')
    
    record.write_to_csv(f'./{environment.design_name}_methodology6.csv')