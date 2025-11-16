"""
ConversationRunner class for managing test bench generation and coverage evaluation workflows.
"""

import logging
import os
import re
from typing import Optional
import argparse

from transformers import AutoTokenizer
from llm_verif.environment import Environment
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

    async def batch_generate_testplans(self, testplan_prompt: str, batch_count: int) -> str:
        logging.info(f"===== BATCH GENERATING {batch_count} TESTPLANS =====")
        
        generated_testplans = []
        for batch_idx in range(batch_count):
            logging.info(f"\n===== Generating Testplan {batch_idx + 1} of {batch_count} ======\n")
            self.conversation.append_user_message(testplan_prompt, update_stack_pointer=False)
            responses, tokens_generated, gen_time = await self.llm.generate_response_async(
                self.conversation, num_return_sequences=1
            )
            batch_testplan = responses[0]
            generated_testplans.append(batch_testplan)
            logging.info(f"\n===== Testplan {batch_idx + 1} =====")
            logging.info(batch_testplan)
            logging.info(f"===================================\n")
            
            # Remove user message to keep conversation clean
            self.conversation.conversation.pop()
        
        # Synthesize all testplans into one
        logging.info(f"===== Synthesizing {batch_count} Testplans =====")
        
        synthesis_prompt = prompt_templates.synthesize_testplans_prompt(generated_testplans)
        self.conversation.append_user_message(synthesis_prompt, update_stack_pointer=False)
        responses, tokens_generated, gen_time = await self.llm.generate_response_async(
            self.conversation, num_return_sequences=1
        )
        synthesized_testplan = responses[0]
        
        logging.info("\n===== SYNTHESIZED VERIFICATION PLAN =====")
        logging.info(synthesized_testplan)
        logging.info("===================================\n")
        self.conversation.append_assistant_message(synthesized_testplan, slice=False)
        
        # Save the synthesized testplan to file
        testplan_file = os.path.join(self.environment.work_dir, "testplan.txt")
        with open(testplan_file, 'w') as f:
            f.write(synthesized_testplan)
        logging.info(f"===== Synthesized testplan saved to: {testplan_file}\n")
        
        return synthesized_testplan

    def parse_features_from_testplan(self, testplan_text: str) -> list[dict]:
        """
        Parse features from testplan text.

        Returns:
            list[dict]: List of feature dictionaries with 'short_name' and 'full_desc' keys.
        """
        features = []

        # Primary pattern: Look for **Feature N: Name** headers
        feature_pattern = r'\*\*Feature\s+(\d+):\s*([^\n]+)\*\*'
        matches = re.finditer(feature_pattern, testplan_text, re.IGNORECASE | re.MULTILINE)

        feature_positions = []
        for match in matches:
            feature_num = match.group(1)
            feature_name = match.group(2).strip()
            start_pos = match.start()
            feature_positions.append((feature_num, feature_name, start_pos))

        # Extract full feature text between consecutive feature headers
        if feature_positions:
            for i, (num, name, start) in enumerate(feature_positions):
                # Determine end position (start of next feature or end of text)
                end = feature_positions[i + 1][2] if i + 1 < len(feature_positions) else len(testplan_text)

                # Extract full feature description including all testpoints
                feature_text = testplan_text[start:end].strip()

                # Create both short name and full description
                features.append({
                    'short_name': name,
                    'full_desc': feature_text
                })

        # Fallback 1: Try alternate patterns if primary pattern fails
        if not features:
            patterns = [
                r'Feature\s+(\d+):\s*([^\n]+)',          # Feature N: Name
                r'(\d+)\.\s+Feature:\s*([^\n]+)',        # N. Feature: Name
            ]

            for pattern in patterns:
                matches = list(re.finditer(pattern, testplan_text, re.IGNORECASE | re.MULTILINE))
                if matches:
                    for i, match in enumerate(matches):
                        num, name = match.group(1), match.group(2).strip()
                        start = match.start()
                        end = matches[i + 1].start() if i + 1 < len(matches) else len(testplan_text)
                        feature_text = testplan_text[start:end].strip()

                        features.append({
                            'short_name': name,
                            'full_desc': feature_text
                        })
                    break

        # Fallback 2: Split by Test Objective if no features found
        if not features:
            objective_pattern = r'Test Objective:\s*([^\n]+)'
            objectives = re.findall(objective_pattern, testplan_text, re.MULTILINE)
            if objectives:
                # This is a rough fallback - just use feature names
                for i, obj in enumerate(objectives):
                    features.append({
                        'short_name': obj.strip(),
                        'full_desc': f"Feature {i+1}: {obj.strip()}"
                    })

        # Final fallback: Treat entire testplan as one feature
        if not features:
            full = "Feature 1: Complete Design Verification\n" + testplan_text
            features.append({
                'short_name': "Complete Design Verification",
                'full_desc': full
            })

        return features

    async def generate_and_evaluate(
        self, prompt: str, run: int, iteration: int, json: bool = True,
        batch_size: int = 1, set_stack_pointer: bool = False, sim_runs: int = 1, feature: str = "N/A"
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
            feature (str): Feature being tested (for tracking).

        Returns:
            CoverageResponse: The best coverage response from the batch.
        """
        csv_path = f"{self.environment.work_dir}/{self.environment.csv_path}"

        if not self.conversation:
            raise ValueError("ConversationManager is not initialized.")

        logging.info(f"Prompt: {prompt}")
        self.conversation.append_user_message(prompt, update_stack_pointer=set_stack_pointer)
        responses, tokens_generated, gen_time = await self.llm.generate_response_async(
            self.conversation, num_return_sequences=1 if not json else batch_size
        )
        logging.info(f"Responses: {responses}")
        logging.info(f"Tokens / second: {tokens_generated / gen_time}")

        selected: CoverageResponse = CoverageResponse()
        if json:
            json_responses: list[str | CoverageResponse] = [
                self.parse_json_response(response) for response in responses
            ]

            for i, response in enumerate(json_responses):
                if isinstance(response, CoverageResponse):
                    self.record.update_dataframe(
                        response, self.llm.temperature, self.llm.top_p, run, iteration, i,
                        tokens_generated, gen_time, feature
                    )

            self.record.write_to_csv(csv_path)

            successful_responses: list[str] = list(filter(lambda x: isinstance(x, str), json_responses)) # type: ignore

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
                        tokens_generated, gen_time, feature
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

    async def run_coverage_refinement(
        self,
        run_index: int,
        iteration: int,
        initial_coverage: "CoverageResponse",
        mode: str = "standalone"
    ) -> tuple[int, "CoverageResponse"]:
        """
        Improve coverage through iterative generation.

        Args:
            run_index (int): Current run index
            iteration (int): Starting iteration number
            initial_coverage (CoverageResponse): The current coverage to improve upon
            mode (str): Refinement mode

        Returns:
            tuple[int, CoverageResponse]: (final_iteration_number, final_coverage_response)
        """
        logging.info("=" * 80)
        logging.info("STARTING COVERAGE REFINEMENT LOOP")
        logging.info(f"Initial coverage: {initial_coverage.total_coverage}%")
        logging.info(f"Target coverage: 100.0%")
        logging.info(f"Max refinement iterations: {self.environment.max_refinement_iterations}")
        logging.info("=" * 80)

        current_coverage = initial_coverage
        refinement_iter = 0
        COVERAGE_TARGET = 100.0

        while (current_coverage.total_coverage < COVERAGE_TARGET
               and refinement_iter < self.environment.max_refinement_iterations):

            logging.info(f"\n--- Refinement Iteration {refinement_iter + 1}/{self.environment.max_refinement_iterations} ---")

            # Generate refinement prompt based on coverage holes
            if not current_coverage.success:
                # If there's an error, use error prompt
                prompt = prompt_templates.error_prompt(
                    current_coverage.error_code,
                    current_coverage.error_message
                )
                logging.info("Using error prompt for refinement")
            else:
                # Extract coverage feedback and generate refinement prompt
                prompt = prompt_templates.iter_prompt(
                    current_coverage,
                    self.environment.design_module_name,
                    self.llm.simulator,
                    self.args.work_dir
                )
                logging.info("Using coverage-driven refinement prompt")

            # Generate and evaluate refinement testbench
            feature_name = f"Refinement_{refinement_iter + 1}"
            if mode == "feature":
                feature_name = f"Feature_Refinement_{refinement_iter + 1}"

            logging.info(f"Generating refinement testbench: {feature_name}")

            current_coverage = await self.generate_and_evaluate(
                prompt,
                run_index,
                iteration + refinement_iter,
                batch_size=self.environment.batch_size,
                sim_runs=self.args.sim_runs,
                feature=feature_name
            )

            logging.info(f"Refinement iteration {refinement_iter + 1} coverage: {current_coverage.total_coverage}%")

            # After generating refinement testbench, merge with all previous coverage
            if self.args.merge_coverage and current_coverage.success:
                try:
                    merged_response = self.llm.simulator.merge_and_parse_run_coverage(
                        design_name=self.environment.design_name,
                        work_dir=self.environment.store.storage_path if self.environment.store else self.args.design,
                        run_idx=run_index,
                        max_iterations=iteration + refinement_iter + 1,
                        batch_size=self.environment.batch_size,
                        sim_runs=self.args.sim_runs,
                        design_dir=self.args.design,
                        use_store=self.environment.store is not None
                    )

                    # Update current coverage with merged result
                    current_coverage = merged_response
                    self.record.update_run_merge_coverage(merged_response, run_index)

                    logging.info(f"Merged coverage after refinement: {merged_response.total_coverage}%")
                except Exception as e:
                    logging.error(f"Failed to merge coverage during refinement: {e}")

            refinement_iter += 1

            # Check if we've reached the target
            if current_coverage.total_coverage >= COVERAGE_TARGET:
                logging.info(f"Coverage target {COVERAGE_TARGET}% reached!")
                break

        logging.info("=" * 80)
        logging.info("COVERAGE REFINEMENT COMPLETE")
        logging.info(f"Final coverage: {current_coverage.total_coverage}%")
        logging.info(f"Refinement iterations used: {refinement_iter}/{self.environment.max_refinement_iterations}")
        logging.info("=" * 80)

        return (iteration + refinement_iter, current_coverage)

    async def run_conversation(self, run_index: int):
        """
        Execute a single run of test bench generation and coverage evaluation.

        Args:
            run_index (int): Index of the current run.
        """
        temperature = self.args.temperature
        top_p = 0.7
        cov = CoverageResponse(True, 0, "")

        self.conversation = ConversationManager(
            self.tokenizer, 
            prompt_templates.system_prompt(
                self.environment.design_specification,
                self.environment.module_header
            )
        )

        logging.info(f"Length of conversation: {self.conversation.length()}")
        logging.info(f"Stack pointer: {self.conversation.stack_pointer}")

        valid_iterations = 0
        iteration = 0
        features = []
        testplan_text = ""

        # Stage 1: Generate verification plan (if testplan is enabled)
        if self.environment.testplan:
            testplan_prompt = prompt_templates.verification_plan_prompt(
                self.environment.design_specification, self.environment.module_header
            )
            logging.info(f"Testplan prompt: {testplan_prompt}")

            # Batch generate multiple testplans (MAX: 10)
            testplan_batch_count = self.args.testplan_batch if self.args.testplan_batch > 1 and self.args.testplan_batch <= 10 else 1

            if testplan_batch_count > 1:
                testplan_text = await self.batch_generate_testplans(testplan_prompt, testplan_batch_count)
            else:
                # Single testplan generation (original behavior)
                self.conversation.append_user_message(testplan_prompt, update_stack_pointer=False)
                responses, tokens_generated, gen_time = await self.llm.generate_response_async(
                    self.conversation, num_return_sequences=1
                )
                testplan_text = responses[0]
                logging.info("\n===== VERIFICATION PLAN =====")
                logging.info(testplan_text)
                logging.info("===================================\n")
                self.conversation.append_assistant_message(testplan_text, slice=False)
                
                # Save the testplan to work dir
                testplan_file = os.path.join(self.environment.work_dir, "testplan.txt")
                with open(testplan_file, 'w') as f:
                    f.write(testplan_text)
                logging.info(f"===== Testplan saved to: {testplan_file}\n")
            
            # Parse features from the testplan (works for both single and synthesized)
            features = self.parse_features_from_testplan(testplan_text)
            logging.info(f"\n===== Identified {len(features)} Features =====")
            for i, feature in enumerate(features, 1):
                logging.info(f"  {i}. {feature['short_name']}")
            logging.info("=========================================\n")
            
            iteration += 1
        else:
            # No testplan - use original single testbench approach
            testbench_prompt = prompt_templates.first_testbench_prompt(
                self.environment.design_specification, self.environment.module_header
            )
            logging.info(f"Testbench prompt: {testbench_prompt}")
            features = ["Single Testbench (No Feature-Based Testing)"]

        logging.info(f"Length of conversation: {self.conversation.length()}")
        logging.info(f"Stack pointer: {self.conversation.stack_pointer}")

        # Feature-based testbench generation
        if self.environment.testplan and features:
            for feature_idx, feature in enumerate(features):
                logging.info(f"\n====== GENERATING TESTBENCH FOR: {feature['short_name']}")

                # Generate feature-specific testbench prompt (use full description for LLM context)
                feature_prompt = prompt_templates.feature_testbench_prompt(
                    feature['full_desc'],
                    feature_idx + 1,
                    len(features),
                    self.environment.design_specification,
                    self.environment.module_header
                )

                # Generate and evaluate testbench for this feature (use short name for CSV)
                cov = await self.generate_and_evaluate(
                    feature_prompt,
                    run_index,
                    iteration,
                    batch_size=self.environment.batch_size,
                    sim_runs=self.args.sim_runs,
                    feature=feature['short_name']
                )
                
                # Retry logic for failed feature testbenches
                feature_attempt = 1  # We already made 1 attempt above

                while not cov.success and feature_attempt < self.args.max_iterations:
                    feature_attempt += 1
                    logging.info(f"\n===== {feature['short_name']} attempt {feature_attempt} FAILED. Retrying with error feedback...\n")

                    iteration += 1

                    # Generate error-specific prompt based on the failure type
                    error_retry_prompt = prompt_templates.error_prompt(cov.error_code, cov.error_message)

                    # Add context about the feature we're still trying to test (use full description)
                    feature_context = f"\nReminder: You are generating a testbench for {feature['full_desc']}. Focus on this specific feature.\n\n"
                    error_retry_prompt = feature_context + error_retry_prompt

                    # Retry with error feedback (use short name with attempt number for CSV)
                    cov = await self.generate_and_evaluate(
                        error_retry_prompt,
                        run_index,
                        iteration,
                        batch_size=self.environment.batch_size,
                        sim_runs=self.args.sim_runs,
                        feature=f"{feature['short_name']} (Attempt {feature_attempt})"
                    )

                    if cov.success:
                        logging.info(f"===== {feature['short_name']} testbench successful on attempt {feature_attempt} - Coverage: {cov.total_coverage}%")
                        break

                # Track successful feature testbenches
                if cov.success:
                    valid_iterations += 1
                    if feature_attempt == 1:
                        logging.info(f"===== {feature['short_name']} testbench successful - Coverage: {cov.total_coverage}%")
                else:
                    logging.info(f"===== {feature['short_name']} testbench failed after {feature_attempt} attempts - Error: {cov.error_message}")
                
                iteration += 1
                
                # Check if we should stop early due to max_valid_iter
                if valid_iterations >= self.args.max_valid_iter:
                    logging.info(f"\n===== Reached max_valid_iter={self.args.max_valid_iter}. Stopping feature testing.")
                    logging.info(f"===== Tested {feature_idx + 1} out of {len(features)} features.\n")
                    break

                logging.info(f"Length of conversation: {self.conversation.length()}")
                logging.info(f"Stack pointer: {self.conversation.stack_pointer}")

            # Merge coverage across all features
            # Use simulator-agnostic merge_and_parse_run_coverage with actual iteration count
            if self.args.merge_coverage:
                try:
                    merged_response = self.llm.simulator.merge_and_parse_run_coverage(
                        design_name=self.environment.design_name,
                        work_dir=self.environment.store.storage_path if self.environment.store else self.args.design,
                        run_idx=run_index,
                        max_iterations=iteration,  # Use actual iteration count reached
                        batch_size=self.environment.batch_size,
                        sim_runs=self.args.sim_runs,
                        design_dir=self.args.design,
                        use_store=self.environment.store is not None
                    )

                    logging.info("Feature-based merged coverage generated successfully.")
                    logging.info(f"\n====== TOTAL COVERAGE ACROSS ALL FEATURES: {merged_response.total_coverage}%")
                    self.record.update_run_merge_coverage(merged_response, run_index)

                    # Coverage refinement after feature generation (testplan mode)
                    if merged_response.total_coverage < 100.0:
                        logging.info("\n" + "=" * 80)
                        logging.info("INITIATING POST-FEATURE COVERAGE REFINEMENT")
                        logging.info(f"Current merged coverage: {merged_response.total_coverage}%")
                        logging.info(f"Target: 100.0%")
                        logging.info("=" * 80 + "\n")

                        iteration, cov = await self.run_coverage_refinement(
                            run_index=run_index,
                            iteration=iteration,
                            initial_coverage=merged_response,
                            mode="standalone"
                        )

                        # Update merged_response with final refined coverage
                        merged_response = cov

                except Exception as e:
                    logging.error(f"===== Failed to generate merged feature coverage: {e}")
        else:
            # Original single testbench approach (no features)
            if cov.success or not self.environment.testplan:
                cov = await self.generate_and_evaluate(
                    testbench_prompt if not self.environment.testplan else prompt_templates.first_testbench_prompt(
                        self.environment.design_specification, self.environment.module_header
                    ), 
                    run_index, 
                    iteration, 
                    batch_size=self.environment.batch_size, 
                    sim_runs=self.args.sim_runs, 
                    feature="Single Testbench"
                )
                if cov.success:
                    valid_iterations += 1

        logging.info(f"Length of conversation: {self.conversation.length()}")
        logging.info(f"Stack pointer: {self.conversation.stack_pointer}")

        # Unified Coverage Refinement (for both testplan and non-testplan modes)
        iteration += 1
        first_success = True
        if not self.environment.testplan:
            if cov.error_code == 0 and first_success:
                first_success = False
                valid_iterations += 1
                if not self.environment.no_design_prompt:
                    self.conversation.update_system_prompt(
                        prompt_templates.system_prompt(
                            self.environment.design_specification,
                            self.environment.module_header,
                            self.environment.all_design_file_paths
                        )
                    )

            # Run coverage refinement
            logging.info("\n" + "=" * 80)
            logging.info("INITIATING COVERAGE REFINEMENT (Non-Testplan Mode)")
            logging.info(f"Current coverage: {cov.total_coverage}%")
            logging.info(f"Target: 100.0%")
            logging.info("=" * 80 + "\n")

            iteration, cov = await self.run_coverage_refinement(
                run_index=run_index,
                iteration=iteration,
                initial_coverage=cov,
                mode="standalone"
            )

        # Merged Coverage Logic (only for non-testplan mode)
        # For testplan mode, feature-based merging already happened above
        if self.args.merge_coverage and not self.environment.testplan:
            try:
                merged_response = self.llm.simulator.merge_and_parse_run_coverage(
                    design_name=self.environment.design_name,
                    work_dir=self.environment.store.storage_path if self.environment.store else self.args.design,
                    run_idx=run_index,
                    max_iterations=iteration,
                    batch_size=self.environment.batch_size,
                    sim_runs=self.args.sim_runs,
                    design_dir=self.args.design,
                    use_store=self.environment.store is not None
                )
                
                logging.info("Merged coverage generated successfully.")
                self.record.update_run_merge_coverage(merged_response, run_index)

            except Exception as e:
                logging.error(f"Failed to generate merged coverage: {e}")

        # Final Write to CSV
        self.record.update_run_max_coverage(run_index)
        self.record.update_run_average_total_coverage(run_id=run_index)
        self.record.write_to_csv(f'./{self.environment.csv_path}')
