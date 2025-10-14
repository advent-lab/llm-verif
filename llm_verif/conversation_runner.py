"""
ConversationRunner class for managing test bench generation and coverage evaluation workflows.
"""

import logging
import os
from typing import Optional
import argparse

from transformers import AutoTokenizer
from llm_verif.environment import Environment
from llm_verif.questasim import QuestaSim
from llm_verif.simulator import CoverageResponse
from llm_verif.modelchat import ModelChat
import llm_verif.prompt_templates as prompt_templates
from llm_verif.record import Record
from llm_verif.conversation_manager import ConversationManager


class ConversationRunner:
    """
    Manages the conversation flow for test bench generation and iterative refinement.
    """

    def __init__(self, llm: ModelChat, environment: Environment, record: Record, args: argparse.Namespace):
        """
        Initialize the ConversationRunner.

        Args:
            llm (ModelChat): The LLM model chat interface.
            environment (Environment): The environment containing design specifications.
            record (Record): The record object for tracking results.
            args (argparse.Namespace): Command-line arguments.
        """
        self.llm = llm
        self.environment = environment
        self.record = record
        self.args = args
        self.tokenizer = AutoTokenizer.from_pretrained(environment.tokenizer_id, use_fast=False)
        self.conversation: Optional[ConversationManager] = None

    def parse_json_response(self, response: str) -> str | CoverageResponse:
        """
        Parse the JSON response from ModelChat and handle errors.

        Args:
            response (str): The JSON response string.

        Returns:
            str | CoverageResponse: Parsed test bench code or error response.
        """
        parsed_response, status = ModelChat.convert_json_response_to_dict(response)
        if status == 0:  # Valid JSON
            test_bench_code = parsed_response.get("test bench", "")
            test_bench_code = test_bench_code.replace('\\"', '"')
            return test_bench_code
        else:
            error_message = parsed_response.get("error", "JSON parsing error.")
            return CoverageResponse(False, 4, error_message)

    def evaluate_coverage(
        self, test_bench_code: str | None, tb_name: str, run: int, iteration: int, batch: int, sim_runs: int = 1
    ) -> CoverageResponse:
        """
        Evaluate the coverage for a generated test bench.

        Args:
            test_bench_code (str | None): The test bench code to evaluate.
            tb_name (str): The test bench file name.
            run (int): The current run index.
            iteration (int): The current iteration index.
            batch (int): The batch index.
            sim_runs (int): Number of simulation runs.

        Returns:
            CoverageResponse: The coverage evaluation result.
        """
        if not test_bench_code:
            return CoverageResponse(False, 4, "Empty test bench. Likely due to a JSON Decode error.")

        try:
            data_point = self.environment.dataset.get_data_point(self.environment.design_name)
            cov = self.llm.get_coverage(
                test_bench_code, self.environment.work_dir, tb_name, data_point,
                self.environment.store, batch, sim_runs=sim_runs
            )
            return cov
        except KeyError as e:
            return CoverageResponse(False, 4, f"Key error: {e}")

    def generate_and_evaluate(
        self, prompt: str, run: int, iteration: int, json: bool = True,
        batch_size: int = 1, set_stack_pointer: bool = False, sim_runs: int = 1
    ) -> CoverageResponse:
        """
        Generate a test bench and evaluate its coverage.

        Args:
            prompt (str): The prompt to send to the LLM.
            run (int): The current run index.
            iteration (int): The current iteration index.
            json (bool): Whether to expect JSON formatted responses.
            batch_size (int): Number of responses to generate.
            set_stack_pointer (bool): Whether to set the stack pointer.
            sim_runs (int): Number of simulation runs.

        Returns:
            CoverageResponse: The best coverage response from the batch.
        """
        csv_path = f"{self.environment.work_dir}/{self.environment.csv_path}"

        if not self.conversation:
            raise ValueError("ConversationManager is not initialized.")

        print(prompt)
        self.conversation.append_user_message(prompt, update_stack_pointer=set_stack_pointer)
        responses, tokens_generated, gen_time = self.llm.generate_response(
            self.conversation, num_return_sequences=1 if not json else batch_size
        )
        print(responses)
        print(f"Tokens / second: {tokens_generated / gen_time}\n")

        selected: CoverageResponse = CoverageResponse()
        if json:
            json_responses: list[str | CoverageResponse] = [
                self.parse_json_response(response) for response in responses
            ]

            for i, response in enumerate(json_responses):
                if isinstance(response, CoverageResponse):
                    self.record.update_dataframe(
                        response, self.llm.temperature, self.llm.top_p, run, iteration, i,
                        tokens_generated, gen_time
                    )

            self.record.write_to_csv(csv_path)

            successful_responses: list[str] = list(str(filter(lambda x: isinstance(x, str), json_responses)))

            # If successful responses isn't empty, find the best one
            if len(successful_responses) != 0:
                tb_names = [
                    f'tb_llm_{self.environment.design_name}_{run}_{iteration}_{i}.v'
                    for i in range(len(successful_responses))
                ]

                coverage_responses: list[CoverageResponse] = [
                    self.evaluate_coverage(test_bench_code, tb_name, run, iteration, i, sim_runs=sim_runs)
                    for i, (test_bench_code, tb_name) in enumerate(zip(successful_responses, tb_names))
                ]

                max_coverage: tuple[float, str, CoverageResponse] = (0, "", CoverageResponse())
                for i, response in enumerate(coverage_responses):
                    if response.total_coverage >= max_coverage[0]:
                        max_coverage = (response.total_coverage, successful_responses[i], response)

                self.conversation.append_assistant_message(
                    max_coverage[1], slice=(True and self.environment.remove_polluted_context)
                )

                for i, response in enumerate(coverage_responses):
                    self.record.update_dataframe(
                        response, self.llm.temperature, self.llm.top_p, run, iteration, i,
                        tokens_generated, gen_time
                    )

                selected = max_coverage[2]
            else:  # If responses is empty, pick a bad response
                bad_response = json_responses[0] if isinstance(json_responses[0], CoverageResponse) else CoverageResponse(False, 4, "Unexpected JSON Error.")

                self.conversation.append_assistant_message(bad_response.error_message, slice=False)

                selected = bad_response

            self.record.write_to_csv(csv_path)
            return selected
        else:
            self.conversation.append_assistant_message(responses[0], slice=False)

        return CoverageResponse(True, 0, "", [], 0)

    def run_conversation(self, run_index: int):
        """
        Execute a single run of test bench generation and coverage evaluation.

        Args:
            run_index (int): Index of the current run.
        """
        temperature = self.args.temperature
        top_p = 0.7
        cov = CoverageResponse(True, 0, "")

        self.conversation = ConversationManager(self.tokenizer, prompt_templates.system_prompt(self.environment.design_specification, self.environment.module_header))

        print("Length of conversation: ", self.conversation.length())
        print("Stack pointer: ", self.conversation.stack_pointer)

        valid_iterations = 0
        iteration = 0

        # Stage 1: Generate verification plan (if testplan is enabled)
        if self.environment.testplan:
            testplan_prompt, testbench_prompt = prompt_templates.verif_and_testbench_prompt(self.environment.crt)
            print(testplan_prompt)
            print(testbench_prompt)
            cov = self.generate_and_evaluate(testplan_prompt, run_index, iteration, json=False)
            iteration += 1
        else:
            testbench_prompt = prompt_templates.first_testbench_prompt(
                self.environment.design_specification, self.environment.module_header
            )
            print(testbench_prompt)

        print("Length of conversation: ", self.conversation.length())
        print("Stack pointer: ", self.conversation.stack_pointer)

        # Stage 2: Generate test bench
        if cov.success:
            cov = self.generate_and_evaluate(
                testbench_prompt, run_index, iteration, batch_size=self.environment.batch_size,
                sim_runs=self.args.sim_runs
            )
            if cov.success:
                valid_iterations += 1

        print("Length of conversation: ", self.conversation.length())
        print("Stack pointer: ", self.conversation.stack_pointer)

        # Iterative Refinement
        iteration += 1
        first_success = True
        while (self.record.max_cov < 100 and iteration <= self.args.max_iterations
               and valid_iterations < self.args.max_valid_iter):

            # The stack pointer should point to the last user message
            if cov.error_code == 0 and first_success:
                first_success = False
                valid_iterations += 1
                if not self.environment.no_design_prompt:
                    # Add design prompt to end of conversation
                    self.conversation.update_system_prompt(
                        prompt_templates.system_prompt(self.environment.design_specification, self.environment.module_header, self.environment.all_design_file_paths)
                    )

            if not cov.success:
                prompt = prompt_templates.error_prompt(cov.error_code, cov.error_message)
            else:
                prompt = prompt_templates.iter_prompt(
                    cov,
                    self.environment.design_module_name,
                    self.llm.simulator,
                    self.args.work_dir
                )
            print(prompt)

            # This call adds 2 prompts to the conversation: the next user prompt and the response
            cov = self.generate_and_evaluate(
                prompt, run_index, iteration, batch_size=self.environment.batch_size
            )

            iteration += 1
            print("Length of conversation: ", self.conversation.length())
            print("Stack pointer: ", self.conversation.stack_pointer)

        # Merged Coverage Logic
        if self.args.merge_coverage:
            self._generate_merged_coverage(run_index, iteration)

        # Final Write to CSV
        self.record.update_run_max_coverage(run_index)
        self.record.update_run_average_total_coverage(run_id=run_index)
        self.record.write_to_csv(f'./{self.environment.csv_path}')

    def _generate_merged_coverage(self, run_index: int, iteration: int):
        """
        Generate merged coverage report for all iterations.

        Args:
            run_index (int): The run index.
            iteration (int): The final iteration count.
        """
        try:
            log_name = f"{self.args.work_dir}/merged_coverage_{self.environment.design_name}_{run_index}"

            # Check FileStore for UCDB files
            if self.environment.store:
                stored_ucdb_files = [
                    os.path.join(
                        self.args.work_dir,
                        f"tb_llm_{self.environment.design_name}_{run_index}_{i}_{j}_{k}.ucdb"
                    )
                    for i in range(iteration)
                    for j in range(self.environment.batch_size)
                    for k in range(self.args.sim_runs)
                ]
            else:
                stored_ucdb_files = [
                    f"{self.args.design}/tb_llm_{self.environment.design_name}_{run_index}_{i}_{j}_{k}.ucdb"
                    for i in range(iteration)
                    for j in range(self.environment.batch_size)
                    for k in range(self.args.sim_runs)
                ]

            # Filter for existing UCDB files
            coverage_dbs = [file for file in stored_ucdb_files if os.path.exists(file)]

            if not coverage_dbs:
                logging.warning("No UCDB files found for merging coverage.")
                return

            # Call QuestaSim to merge coverage
            merge_output = self.llm.simulator.generate_merged_coverage_report(
                self.environment.design_module_name,
                coverage_dbs,
                f"{log_name}.ucdb",
                f"{log_name}_report.txt"
            )

            logging.info("Merged coverage generated successfully.")
            # Parse merged coverage
            merged_coverage, total_coverage = QuestaSim.parse_coverage_report(f"{log_name}_report.txt")
            self.record.update_run_merge_coverage(
                CoverageResponse(True, 0, "Merged successfully", merged_coverage, total_coverage), run_index
            )

        except Exception as e:
            logging.error(f"Failed to generate merged coverage: {e}")
