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
from src.prompt_templates import m2_prompts, m3_prompt, design_prompt, error_prompt
from src.eval_runs_util import Record

def parse_json_response(response: str) -> tuple[str, CoverageResponse]:
    """
    Parse the JSON response from LlamaChat and handle errors.
    """
    parsed_response, status = LlamaChat.convert_json_response_to_dict(response)
    if status == 0:  # Valid JSON
        test_bench_code = parsed_response[0].get("test bench", "")
        return test_bench_code, None
    else:
        error_message = parsed_response[0].get("error", "JSON parsing error.")
        return None, CoverageResponse(False, 4, error_message)


def evaluate_coverage(
    test_bench_code: str, tb_path: str, environment: Environment, llama: LlamaChat, run: int, iteration: int
) -> CoverageResponse:
    """
    Evaluate the coverage for a generated test bench.
    """
    if not test_bench_code:
        return CoverageResponse(False, 4, "Empty test bench. Likely due to a JSON Decode error.")
    
    try:
        data_point = environment.dataset.get_data_point(environment.design_name)
        cov = llama.get_coverage(test_bench_code, tb_path, data_point, environment.store)
        return cov
    except KeyError as e:
        return CoverageResponse(False, 4, f"Key error: {e}")


def generate_and_evaluate(
    conversation: list[dict], prompt: str, llama: LlamaChat, tb_path: str, environment: Environment, 
    record: Record, run: int, iteration: int, json: bool = True
) -> CoverageResponse:
    """
    Generate a test bench and evaluate its coverage.
    """
    conversation.append({"role": "user", "content": prompt})
    response, tokens_generated, gen_time = llama.generate_response(conversation)
    conversation.append({"role": "assistant", "content": response})

    if json:
        test_bench_code, coverage_error = parse_json_response(response)
        if coverage_error:
            record.update_dataframe(coverage_error, llama.temperature, llama.top_p, run, iteration, tokens_generated, gen_time)
            return coverage_error
        
        cov = evaluate_coverage(test_bench_code, tb_path, environment, llama, run, iteration)
        record.update_dataframe(cov, llama.temperature, llama.top_p, run, iteration, tokens_generated, gen_time)
        return cov
    
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
    conversation = [{"role": "system", "content": "You are a verification assistant."}]
    prompt1, prompt2 = m2_prompts(environment.design_specification, environment.module_header)
    
    # Stage 1: Generate verification plan
    tb_path = f'{args.design}/tb_llm_{environment.design_name}_{run_index}.v'
    cov = generate_and_evaluate(conversation, prompt1, llama, tb_path, environment, record, run_index, 0, json=False)

    # Stage 2: Generate test bench
    if cov.success:
        cov = generate_and_evaluate(conversation, prompt2, llama, tb_path, environment, record, run_index, 1)
    
    # Iterative Refinement
    iteration = 2
    while not cov.success or (cov.total_coverage < 100 and iteration <= 12):
        prompt = error_prompt(cov.error_code, cov.error_message) if not cov.success else m3_prompt(environment.all_design_file_paths, cov)
        cov = generate_and_evaluate(conversation, prompt, llama, tb_path, environment, record, run_index, iteration)
        conversation = llama.limit_conversation(conversation)
        iteration += 1

    # Merged Coverage Logic
    if args.merge_coverage:
        try:
            merged_ucdb_path = f"{args.design}/merged_coverage_{environment.design_name}_{run_index}.ucdb"
            log_name = f"{args.design}/merged_coverage_{environment.design_name}_{run_index}"

            # Check FileStore for UCDB files
            if environment.store:
                stored_ucdb_files = [
                    os.path.join(environment.store.storage_path, f"tb_llm_{environment.design_name}_{i}.ucdb")
                    for i in range(iteration)
                ]
            else:
                stored_ucdb_files = [
                    f"{args.design}/tb_llm_{environment.design_name}_{i}.ucdb"
                    for i in range(iteration)
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
    record.update_run_average_total_coverage(run_id=run_index)
    record.write_to_csv(f'./{environment.design_name}_methodology6.csv')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--design', type=str, required=True, help="Path of the design directory.")
    parser.add_argument('-g', '--generations', type=int, required=True, help="Number of test bench generations.")
    parser.add_argument('-c', '--compiler', type=str, required=True, help="Path to QuestaSim compiler.")
    parser.add_argument('--no_sampling', action='store_true', help="Disable sampling for LLM responses.")
    parser.add_argument('-t', '--temperature', type=float, default=0.3, help="Sampling temperature.")
    parser.add_argument('--temperature_function', type=str, default="constant", choices=["constant", "logarithmic", "capped_sigmoid"], help="Temperature function.")
    parser.add_argument('-S', '--seed', type=int, default=None, help="Random seed for reproducibility.")
    parser.add_argument('-m', '--merge-coverage', action='store_true', help="Merge coverage reports.")
    args = parser.parse_args()

    environment = Environment(args.design)
    llama = LlamaChat(
        QuestaSim(args.compiler), do_sample=not args.no_sampling,
        temperature_function=args.temperature_function, temperature=args.temperature,
        top_p=0.7, max_new_tokens=4098, timeout_seconds=1000, seed=args.seed
    )
    record = Record(environment.design_name, "RUN")

    for run_index in range(args.generations):
        print(f"\nStarting Run {run_index}")
        record.reset_run()
        run_conversation(run_index, llama, environment, record, args)


if __name__ == "__main__":
    main()
