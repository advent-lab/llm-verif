from datetime import datetime
from pathlib import Path
import re
from tracemalloc import start
import os
import json
from llm_verif.conversation_manager import ConversationManager
from llm_verif.storage import FileStore
import time
from llm_verif.simulator import Simulator, CoverageResponse
from llm_verif.environment import Environment
from math import exp, log10
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Union

class ModelChat:
    """
    An interface for implementing an LLM model chat class

    Using the interface, you can instantiate API based or local based model's in the generate_response.
    
    Attributes:
        simulator (Simulator): An instance of the Simulator class for running coverage tests.
        model (AutoModelForCausalLM): The loaded Llama model.
        tokenizer (AutoTokenizer): The tokenizer for the Llama model.
        do_sample (bool): Flag to enable sampling during text generation.
        temperature_function (callable): Function to determine the sampling temperature.
        top_p (float): Top-p probability for nucleus sampling.
        max_new_tokens (int): Maximum number of tokens to generate.
        timeout_seconds (int): Timeout for text generation in seconds.
    """

    def __init__(
        self, simulator: Simulator | None, 
        environment: Environment, 
        do_sample: bool, 
        temperature_function: str = "constant",
        temperature: float = 0.3, 
        top_p: float = 0.7, 
        max_new_tokens: int = 4098, 
        timeout_seconds: int = 1000, 
        seed: Union[int, None] = None, 
        skip_load: bool = False
    ):
        """
        Initialize the ModelChat class.

        Args:
            simulator (Simulator): An instance of the Simulator class for running coverage tests.
            do_sample (bool): Whether to enable sampling during generation.
            temperature_function (str): The function used for dynamic temperature scaling. Options: 'constant', 'logarithmic', 'capped_sigmoid'.
            temperature (float): The base temperature for sampling (used if temperature_function is 'constant').
            top_p (float): Top-p probability for nucleus sampling.
            max_new_tokens (int): Maximum number of tokens to generate in a single response.
            timeout_seconds (int): Timeout for text generation in seconds.
            skip_load (bool): FOR TESTING ONLY. For faster testing, set this argument to true to skip loading the model
        """
        self.simulator: Simulator | Any
        self.environment: Environment | Any = environment
        self.llm: Any
        self.tokenizer: Any
        self.do_sample: bool
        self.temperature_function: Callable[[int], float]
        self.temperature: float
        self.top_p: float
        self.max_new_tokens: int
        self.timeout_seconds: float

        self.simulator = simulator
        self.do_sample = do_sample
        self.seed = seed
        self.skip_load = skip_load

        if temperature_function == "constant":
            self.temperature_function = lambda _: temperature
        elif temperature_function == "logarithmic":
            self.temperature_function = ModelChat.logarithmic_temperature
        elif temperature_function == "capped_sigmoid":
            self.temperature_function = ModelChat.capped_sigmoid_temperature
        else:
            raise ValueError(f"Unknown temperature function: {temperature_function}")

        self.top_p = top_p
        self.max_new_tokens = max_new_tokens
        self.timeout_seconds = timeout_seconds

    def load_model(self, seed: Union[int, None] = None) -> tuple[Any, Any]:
        """
        Load the model and tokenizer with quantization settings.

        This method should be implemented if you are using a system where you are loading and configuring the model locally
        instead of using an API.

        Args:
            seed (Union[int, None]): Random seed for reproducibility. Default is None.

        Returns:
            tuple: A tuple containing the loaded model (PreTrainedModel) and tokenizer (PreTrainedTokenizer).

        Raises:
            Exception: If the model or tokenizer fails to load.
        """
        return None, None

    def unload_model(self):
        """
        Unload the Llama model and tokenizer to free up memory.
        """
        del self.llm

    def generate_response(self, conversation_history: ConversationManager, num_return_sequences: int = 1) -> tuple[list[str], int, float]:
        """
        Generate a response from the model given the conversation history.

        Args:
            conversation_history (ConversationManager): The conversation history as a ConversationManager instance.
            num_return_sequences (int): Number of response sequences to generate.

        Returns:
            tuple[list[str], int, float]:
                - The generated responses as a list of strings.
                - The number of tokens in the response.
                - The time taken to generate the response in seconds.

        Raises:
            ValueError: If the conversation history is empty or invalid.
            Exception: For unexpected errors during text generation.
        """

        return [""], 0, 0.0

    async def generate_response_async(self, conversation_history: ConversationManager, num_return_sequences: int = 1) -> tuple[list[str], int, float]:
        """
        Generate a response from the model given the conversation history (async version).

        This is the preferred method for async-compatible backends. Subclasses implementing
        async APIs should override this method.

        Args:
            conversation_history (ConversationManager): The conversation history as a ConversationManager instance.
            num_return_sequences (int): Number of response sequences to generate.

        Returns:
            tuple[list[str], int, float]:
                - The generated responses as a list of strings.
                - The number of tokens in the response.
                - The time taken to generate the response in seconds.

        Raises:
            ValueError: If the conversation history is empty or invalid.
            Exception: For unexpected errors during text generation.
        """
        # Default implementation: call synchronous version
        # Async-native backends should override this method
        return self.generate_response(conversation_history, num_return_sequences)

    @staticmethod
    def convert_json_response_to_dict(generated_response: str) -> tuple[dict[str, Any], int]:
        """
        Extract and parse JSON content from an AI-generated response.

        This method identifies and parses JSON-like content embedded within the model's response.
        If the response contains invalid JSON or no JSON at all, it attempts to extract the most
        plausible JSON segment and returns a default structure for errors.

        Args:
            generated_response (str): The AI-generated response containing JSON-like content.

        Returns:
            Tuple[Dict[str, Any], int]:
                - The parsed JSON object as a dictionary.
                - A status code:
                    - 0: Successfully parsed JSON.
                    - 1: Empty response or no JSON found.
                    - 2: JSON parsing failed.
                    - 3: Other unexpected errors.

        Notes:
            - This function is designed for scenarios where the AI response might contain
              additional non-JSON text before or after the JSON content.
        """
        # Handle empty response
        if not generated_response:
            logging.error("Empty or invalid response received.")
            return {"error": "Empty response"}, 1

        # Attempt to extract JSON-like content
        try:
            # Find the first JSON curly brace
            first_pos = generated_response.find('{')
            if first_pos != -1:
                generated_response = generated_response[first_pos:]
            
            comments_pos = generated_response.find('"comments":')
            
            # Find the first JSON curly brace after comments tag
            last_pos = generated_response.find('}', comments_pos)
            if last_pos != -1 and comments_pos != -1:
                generated_response = generated_response[:last_pos + 1]

            # TODO: Escape all non-terminal double quotes
            pattern = r'{\s*"test bench":\s*"(.*?)",\s*"comments":\s*"(.*?)"\s*}'
            matches = re.match(pattern, generated_response, re.DOTALL)
            if matches:
                parsed_response = matches.group(1)
            else:
                raise RuntimeError(f"Could not parse the response:\n{generated_response}")

            # Parse JSON
            #decoder = json.JSONDecoder(strict=False)
            #parsed_response = decoder.raw_decode(generated_response)
            return {"test bench": parsed_response}, 0

        except json.JSONDecodeError as e:
            logging.error(f"JSONDecodeError: {e}. Response: {generated_response}")
            return {"error": f"Malformed JSON content\n\n{generated_response}"}, 2

        except Exception as e:
            logging.error(f"Unexpected error during JSON parsing: {e}")
            return {"error": f"Unexpected error\n\n{generated_response}"}, 3

    def get_coverage(self, generated_response: str, work_dir: str | Path, tb_name: str, data_point: dict[str, str | list[str]] | None, storage: FileStore | None = None, batch: int = 0, sim_runs: int = 1) -> CoverageResponse:
        if not generated_response:
            return CoverageResponse(False, 4, "Empty test bench (JSON Decode Error)")

        log_stem = tb_name.split('.')[0]
        artifact_plan = self.simulator.plan_artifacts(work_dir, log_stem, sim_runs)

        # Write the generated testbench to a file
        with open(artifact_plan.tb_path, "w+") as testbench_file:
            testbench_file.write(generated_response)

        # Run simulator to get coverage
        coverage_response = self.simulator.run_simulation_flow(
            work_dir=work_dir,
            tb_name=os.path.basename(artifact_plan.tb_path),
            data_point=data_point,
            sim_runs=sim_runs
        )
            
        if storage:
            for p in [
                artifact_plan.tb_path, 
                artifact_plan.compile_log, 
                *artifact_plan.sim_logs,
                *(artifact_plan.per_run_coverage_dbs or []),
                artifact_plan.merged_coverage_db,
                artifact_plan.report_path,
                artifact_plan.annotate_dir,
                artifact_plan.info_path
            ]:
                if p and os.path.exists(p):
                    storage.move(p)

        return coverage_response

    def get_merge_coverage(self, run: int):
        self.simulator.merge_coverage()

    @staticmethod
    def capped_sigmoid_temperature(n: int, T_start: float = 0.2, T_end: float = 0.8, N: int = 9, k: float = 0.9) -> float:
        """
        Calculate a capped sigmoid temperature for dynamic sampling.

        Args:
            n (int): The number of messages in the conversation.
            T_start (float): Starting temperature.
            T_end (float): Maximum temperature.
            N (int): Number of messages where the temperature approaches T_end.
            k (float): Scaling factor.

        Returns:
            float: The computed temperature.
        """
        T = T_start + (T_end - T_start) / (1 + exp(-k * ((n - N) / 2)))
        return min(T, T_end)

    @staticmethod
    def logarithmic_temperature(n: int, T_start: float = 0.2, T_end: float = 0.8, N: int = 26) -> float:
        """
        Compute a logarithmic temperature for sampling.

        Args:
            n (int): The number of messages in the conversation.
            T_start (float): The starting temperature.
            T_end (float): The maximum temperature.
            N (int): The number of messages where the temperature approaches T_end.

        Returns:
            float: The computed temperature.
        """
        T = T_start + (T_end - T_start) * (log10(n + 1) / log10(N + 1))
        return min(T, T_end)
