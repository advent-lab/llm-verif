import logging
import os
import sys
from pathlib import Path

# Add the project root to the PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.environment import Environment
from src.questasim import QuestaSim
from src.simulator import CoverageResponse
from src.llama3_chat import LlamaChat
import argparse
from src.prompt_templates import m1_prompt, m2_prompts, m3_prompt, design_prompt, error_prompt
from src.eval_runs_util import Record

def parse_json_response(response: str) -> str | CoverageResponse:
    """
    Parse the JSON response from LlamaChat and handle errors.
    """
    parsed_response, status = LlamaChat.convert_json_response_to_dict(response)
    if status == 0:  # Valid JSON
        test_bench_code = parsed_response.get("test bench", "")
        return test_bench_code
    else:
        error_message = parsed_response.get("error", "JSON parsing error.")
        return CoverageResponse(False, 4, error_message)


def evaluate_coverage(
    test_bench_code: str | None, tb_path: str, environment: Environment, llama: LlamaChat, run: int, iteration: int, batch: int
) -> CoverageResponse:
    """
    Evaluate the coverage for a generated test bench.
    """
    if not test_bench_code:
        return CoverageResponse(False, 4, "Empty test bench. Likely due to a JSON Decode error.")
    
    try:
        data_point = environment.dataset.get_data_point(environment.design_name)
        cov = llama.get_coverage(test_bench_code, tb_path, data_point, environment.store, batch)
        return cov
    except KeyError as e:
        return CoverageResponse(False, 4, f"Key error: {e}")


def generate_and_evaluate(
    conversation: list[dict], prompt: str, llama: LlamaChat, environment: Environment, 
    record: Record, run: int, iteration: int, json: bool = True, batch_size: int = 1
) -> CoverageResponse:
    """
    Generate a test bench and evaluate its coverage.
    """

    # Print Full Conversation Before Running Each Iteration
    print("\n" + "=" * 80)
    print(f"ITERATION {iteration} (Run {run})")
    print("-" * 80)
    for message in conversation:
        print(f"{message['role'].capitalize()}: {message['content']}\n")
    print("-" * 80)


    print(prompt)
    conversation.append({"role": "user", "content": prompt})
    responses, tokens_generated, gen_time = llama.generate_response(conversation, num_return_sequences=batch_size)
    print(responses)
    print(f"Tokens / second: {tokens_generated / gen_time}\n")

    selected: CoverageResponse = CoverageResponse()
    if json:
        json_responses: list[str | CoverageResponse] = [parse_json_response(response) for response in responses]
        
        for i, response in enumerate(json_responses):
            if isinstance(response, CoverageResponse):
                record.update_dataframe(response, llama.temperature, llama.top_p, run, iteration, i, tokens_generated, gen_time)
                
        record.write_to_csv(f'./{environment.csv_path}')
        
        successful_responses: list[str] = list(filter(lambda x: isinstance(x, str), json_responses)) # type: ignore

        # If successful responses isn't empty, find the best one
        if len(successful_responses) != 0:
            
            tb_paths = [
                f'{environment.design_dir}/tb_llm_{environment.design_name}_{run}_{iteration}_{i}.v' 
                for i in range(len(successful_responses))
            ]
        
            coverage_responses: list[CoverageResponse] = [
                evaluate_coverage(test_bench_code, tb_path, environment, llama, run, iteration, i)
                for i, (test_bench_code, tb_path) in enumerate(zip(successful_responses, tb_paths))
            ]

            
            max_coverage: tuple[float, str, CoverageResponse] = (0, "", CoverageResponse())
            for i, response in enumerate(coverage_responses):
                if response.total_coverage >= max_coverage[0]:
                    max_coverage = (response.total_coverage, successful_responses[i], response)

            conversation.append({"role": "assistant", "content": max_coverage[1]})
            
            for i, response in enumerate(coverage_responses):
                record.update_dataframe(response, llama.temperature, llama.top_p, run, iteration, i, tokens_generated, gen_time)
        
            selected = max_coverage[2]
        else: # If responses is empty, pick a bad response
            bad_response = json_responses[0] if isinstance(json_responses[0], CoverageResponse) else CoverageResponse(False, 4, "Unexpected JSON Error.")
            conversation.append({
                "role": "assistant", 
                "content": bad_response.error_message
            })
            selected = bad_response 
            
        record.write_to_csv(f'./{environment.csv_path}')
        return selected
        
    return CoverageResponse(True, 0, "", [], 0)


def run_conversation(
    run_index: int, llama: LlamaChat, environment: Environment, record: Record, args: argparse.Namespace
):
    """
    Execute a single run of test bench generation and coverage evaluation.

    Args:
        run_index (int): Index of the current run.
        llama (LlamaChat): Instance of the LlamaChat class.
        environment (Environment): The Environment object for the design.
        record (Record): The Record object for storing results.
        args (argparse.Namespace): Command-line arguments.
    """
    temperature = args.temperature
    top_p = 0.7
    cov = CoverageResponse(True, 0, "")
    conversation = [{"role": "system", "content": "You are a verification assistant."}]
    stack_pointer = 1
    print("Length of conversation: ", len(conversation))
    print("Stack pointer: ", stack_pointer)
    
    valid_iterations = 0  
    iteration = 0
    if environment.testplan:
        testplan_prompt, testbench_prompt = m2_prompts(environment.design_specification, environment.module_header)
        print(testplan_prompt)
        print(testbench_prompt)
        # Stage 1: Generate verification plan
        cov = generate_and_evaluate(conversation, testplan_prompt, llama, environment, record, run_index, iteration, json=False)
        iteration += 1
        stack_pointer += 2
    else:
        testbench_prompt = m1_prompt(environment.design_specification, environment.module_header)
        print(testbench_prompt)
    
    print("Length of conversation: ", len(conversation))
    print("Stack pointer: ", stack_pointer)

    # Stage 2: Generate test bench
    if cov.success:
        cov = generate_and_evaluate(conversation, testbench_prompt, llama, environment, record, run_index, iteration, batch_size=environment.batch_size)
        if cov.success:
            valid_iterations += 1
            stack_pointer += 2

    print("Length of conversation: ", len(conversation))
    print("Stack pointer: ", stack_pointer)    

    # Iterative Refinement
    iteration += 1
    first_success = True
    design_prompt_idx = 0
    while record.max_cov < 100 and iteration <= args.max_iterations and valid_iterations < args.max_valid_iter:
        #if cov.success and not has_all_files:
            #conversation = conversation[:(stack_pointer+1)] + [conversation[len(conversation) - 1]]
            #stack_pointer = len(conversation) + 1 # add 1 to account for the m3_prompt that will be added to the conversation history
            #has_all_files = True

        if cov.error_code == 0 and first_success:
            first_success = False
            if args.remove_polluted_context:
                conversation = conversation[:(stack_pointer+1)] + [conversation[-1]]
            valid_iterations += 1
            conversation.append({"role": "user", "content": design_prompt(environment.all_design_file_paths)})
            print(conversation[-1])
            design_prompt_idx = len(conversation) - 1
            if args.remove_polluted_context: 
                stack_pointer = len(conversation) - 1

        prompt = error_prompt(cov.error_code, cov.error_message) if not cov.success else m3_prompt(cov)
        print(prompt)
        cov = generate_and_evaluate(conversation, prompt, llama, environment, record, run_index, iteration, batch_size=environment.batch_size)
        if cov.success and args.remove_polluted_context: 
            conversation.insert(stack_pointer - 1, conversation[design_prompt_idx])
            conversation = conversation[stack_pointer + 1:len(conversation) - 1]
            stack_pointer = len(conversation) - 1
            design_prompt_idx = stack_pointer - 1

        # Call limit_conversation and update indices accordingly
        conversation, stack_pointer, design_prompt_idx = llama.limit_conversation(conversation, stack_pointer=stack_pointer, design_prompt_idx=design_prompt_idx)

        iteration += 1
        print("Length of conversation: ", len(conversation))
        print("Stack pointer: ", stack_pointer)

    # Merged Coverage Logic
    if args.merge_coverage:
        try:
            log_name = f"{environment.store.storage_path}/merged_coverage_{environment.design_name}_{run_index}"

            # Check FileStore for UCDB files
            if environment.store:
                stored_ucdb_files = [
                    os.path.join(environment.store.storage_path, f"tb_llm_{environment.design_name}_{run_index}_{i}_{j}.ucdb")
                    for i in range(iteration)
                    for j in range(environment.batch_size)
                ]
            else:
                stored_ucdb_files = [
                    f"{args.design}/tb_llm_{environment.design_name}_{run_index}_{i}_{j}.ucdb"
                    for i in range(iteration)
                    for j in range(environment.batch_size)
                ]

            # Filter for existing UCDB files
            coverage_dbs = [file for file in stored_ucdb_files if os.path.exists(file)]

            if not coverage_dbs:
                logging.warning("No UCDB files found for merging coverage.")
                return

            # Call QuestaSim to merge coverage
            merge_output = llama.simulator.generate_merged_coverage_report(
                du=environment.design_module_name,
                coverage_dbs=coverage_dbs,
                log_name=log_name,
            )
            logging.info("Merged coverage generated successfully.")
            # Parse merged coverage
            merged_coverage, total_coverage = QuestaSim.parse_coverage_report(f"{log_name}_report.txt")
            record.update_run_merge_coverage(CoverageResponse(True, 0, "Merged successfully", merged_coverage, total_coverage), run_index)

        except Exception as e:
            logging.error(f"Failed to generate merged coverage: {e}")
    
    # Final Write to CSV
    record.update_run_average_total_coverage(run_id=run_index)
    record.write_to_csv(f'./{environment.csv_path}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--design', type=str, required=True, help="Path of the design directory.")
    parser.add_argument('-g', '--generations', type=int, required=True, help="Number of test bench generations.")
    parser.add_argument('-c', '--compiler', type=str, required=True, help="Path to QuestaSim compiler.")
    parser.add_argument('--no_sampling', action='store_true', help="Disable sampling for LLM responses.")
    parser.add_argument('-t', '--temperature', type=float, default=0.3, help="Sampling temperature.")
    parser.add_argument('--temperature_function', type=str, default="constant", choices=["constant", "logarithmic", "capped_sigmoid"], help="Temperature function.")
    parser.add_argument('-S', '--seed', type=int, required=False, help="Random seed for reproducibility.")
    parser.add_argument('-m', '--merge-coverage', action='store_true', help="Merge coverage reports.")
    parser.add_argument('--testplan', action='store_true', help="Enable generating a test plan before generating any test benches.")
    parser.add_argument('--remove_polluted_context', action='store_true', help='Enable the removal of polluted content from the conversation history')
    parser.add_argument('--max_iterations', type=int, default=12, help="Maximum number of iterations for iterative refinement.")
    parser.add_argument('--max_valid_iter', type=int, default=10, help="Maximum number of successful iterations")
    parser.add_argument('-o', '--output', type=str, default="./logs", help="Output directory for log files.")
    parser.add_argument('-b', "--batch_size", type=int, default=1, help="The number of test benches to generate per query.")
    args = parser.parse_args()

    environment = Environment(args)
    record = Record(environment.design_name, "RUN", include_merge_coverage=args.merge_coverage)

    llama = LlamaChat(
        QuestaSim(args.compiler), environment, do_sample=not args.no_sampling,
        temperature_function=args.temperature_function, temperature=args.temperature,
        top_p=0.7, max_new_tokens=4098, timeout_seconds=1000, seed=args.seed
    )

    for run_index in range(args.generations):
        print(f"\nStarting Run {run_index}")
        record.reset_run()
        run_conversation(run_index, llama, environment, record, args)

    if args.merge_coverage:
        try:
            log_name = f"{environment.store.storage_path}/merged_coverage_{environment.design_name}"

            # Check FileStore for UCDB files
            if environment.store:
                stored_ucdb_files = [
                    os.path.join(environment.store.storage_path, f"tb_llm_{environment.design_name}_{i}_{j}_{k}.ucdb")
                    for i in range(args.generations)
                    for j in range(args.max_iterations)
                    for k in range(args.batch_size)
                ]
            else:
                stored_ucdb_files = [
                    f"{args.design}/tb_llm_{environment.design_name}_{i}_{j}_{k}.ucdb"
                    for i in range(args.generations)
                    for j in range(args.max_iterations)
                    for k in range(args.batch_size)
                ]

            # Filter for existing UCDB files
            coverage_dbs = [file for file in stored_ucdb_files if os.path.exists(file)]

            if not coverage_dbs:
                logging.warning("No UCDB files found for merging coverage.")
                return

            # Call QuestaSim to merge coverage
            merge_output = llama.simulator.generate_merged_coverage_report(
                du=environment.design_module_name,
                coverage_dbs=coverage_dbs,
                log_name=log_name,
            )
            logging.info("Merged coverage generated successfully.")
            # Parse merged coverage
            merged_coverage, total_coverage = QuestaSim.parse_coverage_report(f"{log_name}_report.txt")
            record.update_cross_run_merge_coverage(CoverageResponse(True, 0, "Merged successfully", merged_coverage, total_coverage))

        except Exception as e:
            logging.error(f"Failed to generate merged coverage: {e}")
    
    # Final Write to CSV
    record.write_to_csv(f'./{environment.csv_path}')


if __name__ == "__main__":
    main()
