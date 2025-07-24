import logging
import os
import sys
from pathlib import Path

# Add the project root to the PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parents[1]))

from llm_verif import __version__ as VERSION
from llm_verif.environment import Environment
from llm_verif.questasim import QuestaSim
from llm_verif.simulator import CoverageResponse
from llm_verif.chatgpt_chat import ChatGPTChat
import argparse
from llm_verif.record import Record
from llm_verif.util import run_conversation
from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser(description="LLM Test Bench Generator Tool")
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
    parser.add_argument('--dotenv_path', type=str, required=True, help="Path to dotenv file containing required API keys and config.")

    # All other args are optional at parse-time
    parser.add_argument('-d', '--design', type=str, help="Path of the design directory.")
    parser.add_argument('-r', '--runs', type=int, help="Number of runs/conversations.")
    parser.add_argument('-c', '--compiler', type=str, help="Path to EDA compiler.")
    parser.add_argument('--no_sampling', action='store_true', help="Disable sampling for LLM responses.")
    parser.add_argument('-t', '--temperature', type=float, help="Sampling temperature.")
    parser.add_argument('--temperature_function', type=str, choices=["constant", "logarithmic", "capped_sigmoid"], help="Temperature function.")
    parser.add_argument('-S', '--seed', type=int, help="Random seed for reproducibility.")
    parser.add_argument('-m', '--merge-coverage', action='store_true', help="Merge coverage reports.")
    parser.add_argument('--testplan', action='store_true', help="Enable generating a test plan before generating any test benches.")
    parser.add_argument('--remove_polluted_context', action='store_true', help='Enable the removal of polluted content from the conversation history')
    parser.add_argument('--max_iterations', type=int, help="Maximum number of iterations for iterative refinement.")
    parser.add_argument('--max_valid_iter', type=int, help="Maximum number of successful iterations")
    parser.add_argument('-o', '--output', type=str, help="Output directory for log files.")
    parser.add_argument('-b', "--batch_size", type=int, help="The number of test benches to generate per query.")
    parser.add_argument('--id', type=str, help="User specified identifier")
    parser.add_argument("-q", "--quantize", action="store_true", help="Enable quantization.")
    parser.add_argument("--model", type=str, help="LLM model name or path.")
    parser.add_argument("--tokenizer", type=str, help="Tokenizer used for ConversationManager")
    parser.add_argument('--no_design_prompt', action='store_true', help="Disable design prompt.")

    args = parser.parse_args()

    # Load env file
    dotenv_path = args.dotenv_path
    if not os.path.exists(dotenv_path):
        print(f"ERROR: dotenv file not found at '{dotenv_path}'")
        sys.exit(1)

    load_dotenv(dotenv_path)

    # Required keys to enforce (must be in either env or CLI)
    REQUIRED_KEYS = ["design", "compiler", "id"]

    # Validate presence of required options
    missing_keys = []
    for key in REQUIRED_KEYS:
        arg_val = getattr(args, key)
        env_val = os.getenv(key.upper())  # use uppercase by convention
        if arg_val is None and env_val is None:
            missing_keys.append(key)

    if missing_keys:
        print(f"ERROR: Missing required configuration for: {', '.join(missing_keys)}")
        print("You must specify them either as command-line arguments or in the .env file.")
        sys.exit(1)

    # At this point, you can fallback to env for any missing optional args
    def resolve_config(key, default=None, cast=str):
        val = getattr(args, key)
        if val is not None:
            return val
        env_val = os.getenv(key.upper())
        if env_val is not None:
            try:
                return cast(env_val)
            except ValueError:
                print(f"ERROR: Failed to cast {key}='{env_val}' from .env to {cast.__name__}")
                sys.exit(1)
        return default

    args.design = resolve_config("design", cast=str)
    print(f"Using design directory: {args.design}")
    args.runs = resolve_config("runs", default=1, cast=int)
    print(f"Number of runs: {args.runs}")
    args.compiler = resolve_config("compiler", cast=str)
    print(f"Using compiler path: {args.compiler}")
    args.output = resolve_config("output", default="./output", cast=str)
    print(f"Output directory: {args.output}")
    args.no_sampling = resolve_config("no_sampling", default=False, cast=bool)
    print(f"Sampling disabled: {args.no_sampling}")
    args.temperature = resolve_config("temperature", default=0.3, cast=float)
    print(f"Sampling temperature: {args.temperature}")
    args.temperature_function = resolve_config("temperature_function", default="constant", cast=str)
    print(f"Temperature function: {args.temperature_function}")
    args.seed = resolve_config("seed", default=None, cast=int)
    print(f"Random seed: {args.seed}")
    args.merge_coverage = resolve_config("merge_coverage", default=True, cast=bool)
    print(f"Merging coverage reports: {args.merge_coverage}")
    args.testplan = resolve_config("testplan", default=True, cast=bool)
    print(f"Generating test plan: {args.testplan}")
    args.remove_polluted_context = resolve_config("remove_polluted_context", default=False, cast=bool)
    print(f"Removing polluted context: {args.remove_polluted_context}")
    args.max_iterations = resolve_config("max_iterations", default=5, cast=int)
    print(f"Maximum iterations: {args.max_iterations}")
    args.max_valid_iter = resolve_config("max_valid_iter", default=3, cast=int)
    print(f"Maximum valid iterations: {args.max_valid_iter}")
    args.batch_size = resolve_config("batch_size", default=1, cast=int)
    print(f"Batch size: {args.batch_size}")
    args.id = resolve_config("id", default="default", cast=str)
    print(f"User identifier: {args.id}")
    args.quantize = resolve_config("quantize", default=False, cast=bool)
    print(f"Quantization enabled: {args.quantize}")
    args.model = resolve_config("model", default="gpt-4o", cast=str)
    print(f"Using model: {args.model}")
    args.tokenizer = resolve_config("tokenizer", default="meta-llama/Llama-3.3-70B-Instruct", cast=str)
    print(f"Using tokenizer: {args.tokenizer}")
    args.no_design_prompt = resolve_config("no_design_prompt", default=False, cast=bool)
    print(f"Design prompt disabled: {args.no_design_prompt}")

    environment = Environment(args)

    record = Record(
        environment.design_name, 
        identifier=args.id, 
        temp_func=args.temperature_function, 
        testplan=args.testplan, 
        batch_size=args.batch_size, 
        remove_polluted_context=args.remove_polluted_context, 
        run_type="RUN", 
        include_merge_coverage=args.merge_coverage
    )

    llm = ChatGPTChat(
        QuestaSim(args.compiler), 
        environment, 
        do_sample=not args.no_sampling,
        temperature_function=args.temperature_function, 
        temperature=args.temperature,
        top_p=0.7, 
        max_new_tokens=4098, 
        timeout_seconds=1000, 
        seed=args.seed
    )

    for run_index in range(args.runs):
        print(f"\nStarting Run {run_index}")
        record.reset_run()
        run_conversation(run_index, llm, environment, record, args)

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
            merge_output = llm.simulator.generate_merged_coverage_report(
                du=environment.design_module_name,
                coverage_dbs=coverage_dbs,
                log_name=log_name,
            )

            environment.store.move(f"{log_name}.ucdb")
            environment.store.move(f"{log_name}_report.txt")
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
