import logging
import os
import sys
from pathlib import Path
import subprocess

# Add the project root to the PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parents[1]))

# Run 'module load' command
# subprocess.run("module load bittware/questa-23.4", shell=True, check=True, executable="/bin/bash")

# Set the environment variable
# os.environ["LM_LICENSE_FILE"] = "27006@en4228283l.scai.dhcp.asu.edu"

from llm_verif.environment import Environment
from llm_verif.questasim import QuestaSim
from llm_verif.simulator import CoverageResponse
from llm_verif.llama3_chat import LlamaChat
import argparse
from llm_verif.record import Record
from llm_verif.util import run_conversation

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
    parser.add_argument('--id', type=str, required=True, help="User specified identifier")
    parser.add_argument('--no_design_prompt_pointer', action='store_true', required=False, help="Disable the design prompt.")
    parser.add_argument("-q", "--quantize", action="store_true", required=False, help="Enable quantization.")
    parser.add_argument("--model", type=str, required=True)
    parser.add_argument("--tokenizer", type=str, required=False, help="Tokenizer used for ConversationManager")
    parser.add_argument("--dotenv_path", type=str, required=False, help="Path to dotenv file containing required API keys.")
    args = parser.parse_args()

    environment = Environment(args)
    record = Record(environment.design_name, identifier=args.id, temp_func=args.temperature_function, testplan=args.testplan, batch_size=args.batch_size, remove_polluted_context=args.remove_polluted_context, run_type="RUN", include_merge_coverage=args.merge_coverage)

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
