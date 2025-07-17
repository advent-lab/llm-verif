"""
Put citation here
"""


from collections import defaultdict, Counter
from typing import List, Union, Iterable, Dict
import itertools
import numpy as np

import logging
import os
from transformers import AutoTokenizer
from llm_verif.environment import Environment
from llm_verif.questasim import QuestaSim
from llm_verif.simulator import CoverageResponse
from llm_verif.llama3_chat import LlamaChat
import argparse
import llm_verif.prompt_templates as prompt_templates
from llm_verif.record import Record
from llm_verif.conversation_manager import ConversationManager

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
    conversation: ConversationManager, prompt: str, llama: LlamaChat, environment: Environment, 
    record: Record, run: int, iteration: int, json: bool = True, batch_size: int = 1,
    set_stack_pointer: bool = False
) -> CoverageResponse:
    """
    Generate a test bench and evaluate its coverage.
    """

    print(prompt)
    conversation.append_user_message(prompt, update_stack_pointer=set_stack_pointer)
    responses, tokens_generated, gen_time = llama.generate_response(conversation, num_return_sequences=1 if not json else batch_size)
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

            conversation.append_assistant_message(max_coverage[1], slice=(True and environment.remove_polluted_context))
            
            for i, response in enumerate(coverage_responses):
                record.update_dataframe(response, llama.temperature, llama.top_p, run, iteration, i, tokens_generated, gen_time)
        
            selected = max_coverage[2]
        else: # If responses is empty, pick a bad response
            bad_response = json_responses[0] if isinstance(json_responses[0], CoverageResponse) else CoverageResponse(False, 4, "Unexpected JSON Error.")
            
            conversation.append_assistant_message(bad_response.error_message, slice=False)

            selected = bad_response 
            
        record.write_to_csv(f'./{environment.csv_path}')
        return selected
    else:
        conversation.append_assistant_message(responses[0], slice=False)

        
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
    
    tokenizer = AutoTokenizer.from_pretrained(environment.tokenizer_id, use_fast=False)
    conversation = ConversationManager(tokenizer, prompt_templates.system_prompt())

    print("Length of conversation: ", conversation.length())
    print("Stack pointer: ", conversation.stack_pointer)
    
    valid_iterations = 0  
    iteration = 0
    if environment.testplan:
        testplan_prompt, testbench_prompt = prompt_templates.m2_prompts(environment.design_specification, environment.module_header)
        print(testplan_prompt)
        print(testbench_prompt)
        # Stage 1: Generate verification plan
        cov = generate_and_evaluate(conversation, testplan_prompt, llama, environment, record, run_index, iteration, json=False)
        iteration += 1
    else:
        testbench_prompt = prompt_templates.m1_prompt(environment.design_specification, environment.module_header)
        print(testbench_prompt)
    
    print("Length of conversation: ", conversation.length())
    print("Stack pointer: ", conversation.stack_pointer)

    # Stage 2: Generate test bench
    if cov.success:
        cov = generate_and_evaluate(conversation, testbench_prompt, llama, environment, record, run_index, iteration, batch_size=environment.batch_size)
        if cov.success:
            valid_iterations += 1

    print("Length of conversation: ", conversation.length())
    print("Stack pointer: ", conversation.stack_pointer)    

    # Iterative Refinement
    iteration += 1
    first_success = True
    while record.max_cov < 100 and iteration <= args.max_iterations and valid_iterations < args.max_valid_iter:
        #if cov.success and not has_all_files:
            #conversation = conversation[:(stack_pointer+1)] + [conversation[conversation.length() - 1]]
            #stack_pointer = conversation.length() + 1 # add 1 to account for the m3_prompt that will be added to the conversation history
            #has_all_files = True

        # The stack pointer should point to the last user message
        # Design prompt should always point to the design prompt
        if cov.error_code == 0 and first_success:
            first_success = False
            valid_iterations += 1
            if not environment.no_design_prompt:
                # Add design prompt to end of conversation
                conversation.update_system_prompt(prompt_templates.system_prompt(environment.all_design_file_paths))
                
        prompt = prompt_templates.error_prompt(cov.error_code, cov.error_message) if not cov.success else prompt_templates.m3_prompt(cov, environment.design_module_name)
        print(prompt)
        
        # This call adds 2 prompts to the conversation: the next user promtp and the response
        cov = generate_and_evaluate(conversation, prompt, llama, environment, record, run_index, iteration, batch_size=environment.batch_size)

        iteration += 1
        print("Length of conversation: ", conversation.length())
        print("Stack pointer: ", conversation.stack_pointer)

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
            
            environment.store.move(f"{log_name}.ucdb")
            environment.store.move(f"{log_name}_report.txt")
            logging.info("Merged coverage generated successfully.")
            # Parse merged coverage
            merged_coverage, total_coverage = QuestaSim.parse_coverage_report(f"{log_name}_report.txt")
            record.update_run_merge_coverage(CoverageResponse(True, 0, "Merged successfully", merged_coverage, total_coverage), run_index)

        except Exception as e:
            logging.error(f"Failed to generate merged coverage: {e}")
    
    # Final Write to CSV
    record.update_run_max_coverage(run_index)
    record.update_run_average_total_coverage(run_id=run_index)
    record.write_to_csv(f'./{environment.csv_path}')

def estimate_pass_at_k(
        num_samples: Union[int, List[int], np.ndarray],
        num_correct: Union[List[int], np.ndarray],
        k: int
) -> np.ndarray:
    """
    Estimates pass@k of each run and returns them in an arry
    """
    
    # Determine the type of passed arguments
    # Raise error if lengths to not agree
    if isinstance(num_samples, int):
        num_samples_it = itertools.repeat(num_samples, len(num_correct))
    else:
        assert len(num_samples) == len(num_correct)
        num_samples_it = iter(num_samples)

    # Return the estimations
    return np.array([pass_at_k(int(n), int(c), k) for n, c in zip(num_samples_it, num_correct)])

def pass_at_k(n: int, c: int, k: int) -> float:
    """
    Calculates 1 - comb(n - c, k) / comb(n,k)
    """
    if n - c < k:
        return 1.0
    return 1.0 - float(np.prod(1.0 - k / np.arange(n - c + 1, n + 1)))
