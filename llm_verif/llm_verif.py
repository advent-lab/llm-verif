import logging
import os
import sys
from pathlib import Path

# Add the project root to the PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parents[1]))

from llm_verif import __version__ as VERSION
from llm_verif.environment import Environment
from llm_verif.simulator import CoverageResponse
from llm_verif.chatgpt_chat import ChatGPTChat
import argparse
from llm_verif.record import Record
from llm_verif.conversation_runner import ConversationRunner
from llm_verif import prompt_templates
from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser(description="LLM Test Bench Generator Tool")
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
    parser.add_argument('--dotenv_path', type=str, required=True, help="Path to dotenv file containing required API keys and config.")
    parser.add_argument('--backend', type=str, help="Backend to use for LLM.")
    parser.add_argument('--simulator', type=str, default=None, choices=['verilator', 'questasim'], help="Simulator to use for compiling and simulating test benches.")
    parser.add_argument('-v', '--verbose', action='count', default=0, help="Increase verbosity level (can be repeated: -v, -vv, -vvv)")

    # All other args are optional at parse-time
    parser.add_argument('-w', '--work_dir', type=str, help="Working directory for test benches and logs.")
    parser.add_argument('-d', '--design', type=str, help="Path of the design directory.")
    parser.add_argument('-r', '--runs', type=int, help="Number of runs/conversations.")
    parser.add_argument('-c', '--compiler', type=str, help="Path to EDA compiler.")
    parser.add_argument('--no_sampling', action='store_true', default=None, help="Disable sampling for LLM responses.")
    parser.add_argument('-t', '--temperature', type=float, help="Sampling temperature.")
    parser.add_argument('--temperature_function', type=str, choices=["constant", "logarithmic", "capped_sigmoid"], help="Temperature function.")
    parser.add_argument('-S', '--seed', type=int, help="Random seed for reproducibility.")
    parser.add_argument('-m', '--merge-coverage', action='store_true', default=None, help="Merge coverage reports.")
    parser.add_argument('--testplan', action='store_true', default=None, help="Enable generating a test plan before generating any test benches.")
    parser.add_argument('--remove_polluted_context', action='store_true', default=None, help='Enable the removal of polluted content from the conversation history')
    parser.add_argument('--max_iterations', type=int, help="Maximum number of iterations for iterative refinement.")
    parser.add_argument('--max_valid_iter', type=int, help="Maximum number of successful iterations")
    parser.add_argument('-o', '--output', type=str, help="Output directory for log files.")
    parser.add_argument('-b', "--batch_size", type=int, help="The number of test benches to generate per query.")
    parser.add_argument('--id', type=str, help="User specified identifier")
    parser.add_argument("-q", "--quantize", action="store_true", default=None, help="Enable quantization.")
    parser.add_argument("--model", type=str, help="LLM model name or path.")
    parser.add_argument("--tokenizer", type=str, help="Tokenizer used for ConversationManager")
    parser.add_argument('--no_design_prompt', action='store_true', default=None, help="Disable design prompt.")
    parser.add_argument("--sim_runs", type=int, help="Number of times constrained random testbench should be simulated.")
    parser.add_argument("--zero_shot", action='store_true', default=None, help="Enable zero-shot prompting.")
    parser.add_argument("--crt", action='store_true', default=None, help="Enable constrained random testing.")

    args = parser.parse_args()

    # Configure logging based on verbosity level
    # -v    = INFO (default operational info)
    # -vv   = DEBUG (detailed debugging info)
    # -vvv  = DEBUG with even more detail (for developers)
    # no -v = WARNING (only warnings and errors)
    if args.verbose == 0:
        log_level = logging.WARNING
    elif args.verbose == 1:
        log_level = logging.INFO
    else:  # >= 2
        log_level = logging.DEBUG

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    logger = logging.getLogger(__name__)

    # Load env file
    dotenv_path = args.dotenv_path
    if not os.path.exists(dotenv_path):
        logger.error(f"dotenv file not found at '{dotenv_path}'")
        sys.exit(1)

    load_dotenv(dotenv_path)

    # Required keys to enforce (must be in either env or CLI)
    REQUIRED_KEYS = ["design", "compiler", "id", "simulator", "backend"]

    # Validate presence of required options
    missing_keys = []
    for key in REQUIRED_KEYS:
        arg_val = getattr(args, key)
        env_val = os.getenv(key.upper())  # use uppercase by convention
        if arg_val is None and env_val is None:
            missing_keys.append(key)

    if missing_keys:
        logger.error(f"Missing required configuration for: {', '.join(missing_keys)}")
        logger.error("You must specify them either as command-line arguments or in the .env file.")
        sys.exit(1)


    def str_to_bool(val: str) -> bool:
        return val.lower() in ("1", "true", "yes", "on")

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
                logger.error(f"Failed to cast {key}='{env_val}' from .env to {cast.__name__}")
                sys.exit(1)
        return default

    args.work_dir = resolve_config("work_dir", default="./work", cast=str)
    if not os.path.exists(args.work_dir):
        os.makedirs(args.work_dir, exist_ok=True)

    args.work_dir = os.path.abspath(args.work_dir)
    os.chdir(args.work_dir)
    logger.info(f"Using working directory: {args.work_dir}")
    args.design = resolve_config("design", cast=str)
    logger.info(f"Using design directory: {args.design}")
    args.runs = resolve_config("runs", default=1, cast=int)
    logger.info(f"Number of runs: {args.runs}")
    args.compiler = resolve_config("compiler", cast=str)
    logger.info(f"Using compiler path: {args.compiler}")
    args.output = os.path.join(args.work_dir, resolve_config("output", default="output", cast=str))
    logger.info(f"Output directory: {args.output}")
    args.no_sampling = resolve_config("no_sampling", default=False, cast=str_to_bool)
    logger.info(f"Sampling disabled: {args.no_sampling}")
    args.temperature = resolve_config("temperature", default=0.3, cast=float)
    logger.info(f"Sampling temperature: {args.temperature}")
    args.temperature_function = resolve_config("temperature_function", default="constant", cast=str)
    logger.info(f"Temperature function: {args.temperature_function}")
    args.seed = resolve_config("seed", default=None, cast=int)
    logger.info(f"Random seed: {args.seed}")
    args.merge_coverage = resolve_config("merge_coverage", default=True, cast=str_to_bool)
    logger.info(f"Merging coverage reports: {args.merge_coverage}")
    args.testplan = resolve_config("testplan", default=True, cast=str_to_bool)
    logger.info(f"Generating test plan: {args.testplan}")
    args.remove_polluted_context = resolve_config("remove_polluted_context", default=False, cast=str_to_bool)
    logger.info(f"Removing polluted context: {args.remove_polluted_context}")
    args.max_iterations = resolve_config("max_iterations", default=5, cast=int)
    logger.info(f"Maximum iterations: {args.max_iterations}")
    args.max_valid_iter = resolve_config("max_valid_iter", default=3, cast=int)
    logger.info(f"Maximum valid iterations: {args.max_valid_iter}")
    args.batch_size = resolve_config("batch_size", default=1, cast=int)
    logger.info(f"Batch size: {args.batch_size}")
    args.id = resolve_config("id", default="default", cast=str)
    logger.info(f"User identifier: {args.id}")
    args.quantize = resolve_config("quantize", default=False, cast=str_to_bool)
    logger.info(f"Quantization enabled: {args.quantize}")
    args.model = resolve_config("model", default="gpt-4o", cast=str)
    logger.info(f"Using model: {args.model}")
    args.tokenizer = resolve_config("tokenizer", default="meta-llama/Llama-3.3-70B-Instruct", cast=str)
    logger.info(f"Using tokenizer: {args.tokenizer}")
    args.no_design_prompt = resolve_config("no_design_prompt", default=False, cast=str_to_bool)
    logger.info(f"Design prompt disabled: {args.no_design_prompt}")
    args.sim_runs = resolve_config("sim_runs", default=20, cast=int)
    logger.info(f"Simulating constrained random testbench {args.sim_runs} times")
    args.zero_shot = resolve_config("zero_shot", default=False, cast=str_to_bool)
    logger.info(f"Zero-shot prompting enabled: {args.zero_shot}")
    args.crt = resolve_config("crt", default=True, cast=str_to_bool)
    logger.info(f"Constrained random testing enabled: {args.crt}")
    args.simulator = resolve_config("simulator", default="verilator", cast=str)
    logger.info(f"Using simulator: {args.simulator}")

    environment = Environment(args)
    
    if args.simulator == "questasim":
        from llm_verif.questasim import QuestaSim
        sim = QuestaSim(args.compiler, environment.design_module_name)
    elif args.simulator == "verilator":
        from llm_verif.verilator import Verilator
        sim = Verilator(args.compiler, environment.design_module_name)
    else:
        logger.error(f"Unsupported simulator '{args.simulator}'. Supported simulators are 'verilator' and 'questasim'.")
        sys.exit(1)

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

    if args.backend == "openai":

        llm = ChatGPTChat(
            sim,
            environment, 
            do_sample=not args.no_sampling,
            temperature_function=args.temperature_function, 
            temperature=args.temperature,
            top_p=0.7, 
            max_new_tokens=4098, 
            timeout_seconds=1000, 
            seed=args.seed
        )

    elif args.backend == "vllm":
        from .llama3_chat import LlamaChat

        llm = LlamaChat(
            sim,
            environment, 
            do_sample=not args.no_sampling,
            temperature_function=args.temperature_function, 
            temperature=args.temperature,
            top_p=0.7, 
            max_new_tokens=4098, 
            timeout_seconds=1000, 
            seed=args.seed
        )

    else:
        logging.error("No valid backend specified. Use --backend to select 'openai' or 'vllm'.")
        exit(1)

    for run_index in range(args.runs):
        logger.info(f"\n{'='*60}\nStarting Run {run_index}\n{'='*60}")
        record.reset_run()
        runner = ConversationRunner(llm, environment, record, args)
        runner.run_conversation(run_index)

    if args.merge_coverage:
        # Use simulator-agnostic merge method
        merge_result = llm.simulator.merge_and_parse_cross_run_coverage(
            design_name=environment.design_name,
            work_dir=environment.store.storage_path,
            runs=args.runs,
            max_iterations=args.max_iterations,
            batch_size=args.batch_size,
            sim_runs=args.sim_runs,
            design_dir=args.design,
            use_store=environment.store
        )

        if merge_result.success:
            record.update_cross_run_merge_coverage(merge_result)
        else:
            logging.warning(f"Failed to merge coverage: {merge_result.error_message}")
    
    # Final Write to CSV
    record.write_to_csv(f'./{environment.csv_path}')


if __name__ == "__main__":
    main()
