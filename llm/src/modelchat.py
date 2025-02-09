from datetime import datetime
from tracemalloc import start
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig, PreTrainedModel, PreTrainedTokenizer, PreTrainedTokenizerFast
from accelerate import infer_auto_device_map
import torch
import os
import json
from src.storage import FileStore
import time
from src.simulator import Simulator, CoverageResponse
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

    def __init__(self, simulator: Simulator | None, do_sample: bool, temperature_function: str = "constant",
            temperature: float = 0.3, top_p: float = 0.7, max_new_tokens: int = 4098, timeout_seconds: int = 1000, seed: Union[int, None] = None, skip_load: bool = False):
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
        self.model: PreTrainedModel | Any
        self.tokenizer: PreTrainedTokenizer | Any
        self.do_sample: bool
        self.temperature_function: Callable[[int], float]
        self.temperature: float
        self.top_p: float
        self.max_new_tokens: int
        self.timeout_seconds: float

        self.simulator = simulator
        if not skip_load:
            self.model, self.tokenizer = self.load_model(seed=seed)
        self.do_sample = do_sample

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

    def load_model(self, seed: Union[int, None] = None) -> tuple[None, None]:
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
        del self.model

    def generate_response(self, conversation_history: list[dict[str, str]]):
        """
        Generate a response from the model given the conversation history.

        Args:
            conversation_history (list[dict]): The conversation history as a list of messages.

        Returns:
            tuple[str, int, float]: 
                - The generated response as a string.
                - The number of tokens in the response.
                - The time taken to generate the response in seconds.

        Raises:
            ValueError: If the conversation history is empty or invalid.
            Exception: For unexpected errors during text generation.
        """
    
    def generate_batch_responses(self, batch_conversations: list[list[dict[str, str]]]):
        """
        Generate a batch of responses form the model using a batch of inputs
        """ 

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
            # Find the first and last JSON curly braces
            first_pos = generated_response.find('{')
            if first_pos != -1:
                generated_response = generated_response[first_pos:]
            
            last_pos = generated_response.rfind('}')
            if last_pos != -1:
                generated_response = generated_response[:last_pos + 1]

            # Parse JSON
            decoder = json.JSONDecoder(strict=False)
            parsed_response = decoder.raw_decode(generated_response)
            return parsed_response[0], 0

        except json.JSONDecodeError as e:
            logging.error(f"JSONDecodeError: {e}. Response: {generated_response}")
            return {"error": "Malformed JSON content"}, 2

        except Exception as e:
            logging.error(f"Unexpected error during JSON parsing: {e}")
            return {"error": "Unexpected error"}, 3

    def get_coverage(self, generated_response: str, tb_path: str, data_point: dict[str, str | list[str]] | None, storage: FileStore = None):
        """
        Query the simulator to get the code coverage of a given test bench
        """
        pass

    def get_merge_coverage(self, run: int):
        """
        Query the simulator for merge coverage across a run
        """

    def limit_conversation(self, conversation: list[dict[str, str]], context_window: int = 128000) -> list[dict]:
        """
        Limit the conversation memory to ensure it stays within token limits.

        Args:
            conversation (list[dict]): The conversation history.

        Returns:
            list[dict]: The truncated conversation history.

        Raises:
            ValueError: If the conversation is empty or improperly formatted.
        """
        if not conversation or not isinstance(conversation, list):
            logging.error("Empty or invalid conversation passed to limit_conversation.")
            raise ValueError("Conversation must be a non-empty list of messages.")
        
        # Ensure the system prompt is always retained
        if len(conversation) == 1:
            logging.warning("Conversation contains only the system prompt; no truncation needed.")
            return conversation

        current_token_count = sum(len(self.tokenizer.encode(msg["content"])) for msg in conversation)
        print(f"Current token count: {current_token_count}")
        max_token_count = context_window - self.max_new_tokens

        # Trim conversation until within token limits
        while current_token_count > max_token_count and len(conversation) > 1:
            print(f"Trimming conversation to fit within token limits: {current_token_count} > {max_token_count}")
            # Preserve the system message (index 0)
            conversation.pop(1)
            current_token_count = sum(len(self.tokenizer.encode(msg["content"])) for msg in conversation)

        if current_token_count > max_token_count:
            logging.warning("Conversation could not be fully limited within token limits.")

        return conversation


    def parallel_get_coverage(self, responses: str, test_benches: list[str], data_points: list[dict]):
        """
        Run coverage simulations in parallel for multiple test benches.

        Args:
            test_benches (list[str]): List of test bench file paths.
            data_points (list[dict]): List of data points for each simulation.

        Returns:
            list[CoverageResponse]: List of coverage responses.
        """


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
