from datetime import datetime
from urllib import response
# from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig, PreTrainedModel, PreTrainedTokenizer, PreTrainedTokenizerFast
# from accelerate import infer_auto_device_map
import torch
import os
import json
from src.modelchat import ModelChat
from src.storage import FileStore
import time
from src.simulator import Simulator, CoverageResponse
from src.environment import Environment
from src.prompt_templates import design_prompt
from src.conversation_manager import ConversationManager
from math import exp, log10
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Union
from vllm import LLM, SamplingParams 
from pathlib import Path
import re
import torch._dynamo

torch._dynamo.config.suppress_errors = True

logging.basicConfig(level=logging.INFO)

# Set cache location for model
if not os.path.isdir(f"/scratch/{os.environ['USER']}/.cache"):
    os.mkdir(f"/scratch/{os.environ['USER']}/.cache")
os.environ['HUGGINGFACE_HUB_CACHE'] = f"/scratch/{os.environ['USER']}/.cache"

class LlamaChat(ModelChat):
    """
    A class for interacting with the Llama 3.1 language model for conversational AI tasks.

    The LlamaChat class provides functionalities for:
    - Loading and managing the Llama model and tokenizer.
    - Generating responses based on conversation history.
    - Implementing dynamic temperature scaling for sampling.
    - Managing coverage simulations with QuestaSim integration.
    - Logging conversations and managing memory.

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

    def __init__(self, simulator: Simulator | None, environment: Environment, do_sample: bool, temperature_function: str = "constant",
            temperature: float = 0.3, top_p: float = 0.7, max_new_tokens: int = 4098, timeout_seconds: int = 1000, seed: Union[int, None] = None, skip_load: bool = False):
        """
        Initialize the LlamaChat class.

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
        
        super().__init__(
            simulator, 
            environment, 
            do_sample, 
            temperature_function, 
            temperature, 
            top_p, 
            max_new_tokens,
            timeout_seconds, 
            seed,
            skip_load
        )

    def load_model(self, seed: Union[int, None] = None):
        """
        Load the Llama model and tokenizer with quantization settings.

        Args:
            seed (Union[int, None]): Random seed for reproducibility. Default is None.

        Returns:
            tuple: A tuple containing the loaded model (PreTrainedModel) and tokenizer (PreTrainedTokenizer).

        Raises:
            Exception: If the model or tokenizer fails to load.
        """

        # Set PyTorch random seed if provided
        if seed is not None:
            logging.info(f"Setting PyTorch seed to {seed}.")
            torch.manual_seed(seed) # type: ignore
            torch.cuda.manual_seed_all(seed)
            # np.random.seed(seed)

        os.environ['HUGGINGFACE_HUB_CACHE'] = f"/scratch/{os.environ['USER']}/.cache"
        os.environ['HF_HOME'] = f"/scratch/{os.environ['USER']}/.cache"
        # Base model cache directory

        cache_dir = Path(f"/data/grp_aaror112/{self.environment.model_id}/snapshots")
        
        # Get the most recent snapshot directory
        latest_snapshot = sorted(cache_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)[0]

        # Set model_id
        model_id = str(latest_snapshot)

        num_gpus = torch.cuda.device_count()

        if num_gpus == 0:
            raise RuntimeError("No GPUs available.")

        llm = None

        if self.environment.quantized:
            # Load vLLM model
            llm = LLM(
                model=model_id,
                quantization="AWQ",
                tensor_parallel_size=num_gpus,
                gpu_memory_utilization=0.85,
                max_model_len=32766
            )
        else:
             # Load vLLM model
            llm = LLM(
                model=model_id,
                tensor_parallel_size=num_gpus,
                gpu_memory_utilization=0.85,
                max_model_len=32766
            )

        return llm, llm.get_tokenizer()

    def unload_model(self):
        """
        Unload the Llama model and tokenizer to free up memory.
        """
        del self.model

    def generate_response(self, conversation_history: ConversationManager, num_return_sequences=2) -> tuple[list[str], int, float]:
        """
        Generate multiple responses from the model given the conversation history.

        Args:
            conversation_history (list[dict]): The conversation history as a list of messages.
            num_return_sequences (int): Number of different responses to generate for the same input.

        Returns:
            tuple[list[str], int, float]: 
                - A list of generated responses.
                - The total number of tokens in the response batch.
                - The time taken to generate the response in seconds.

        Raises:
            ValueError: If the conversation history is empty or invalid.
            Exception: For unexpected errors during text generation.
        """
        if not conversation_history:
            raise ValueError("Conversation history is required.")

        # Evaluate new temperature based on temperature function
        self.temperature = self.temperature_function(conversation_history.length())

        conversation = conversation_history.get_prompt()

        sampling_params = SamplingParams(
            temperature=self.temperature if self.do_sample else None,
            top_p=self.top_p if self.do_sample else None,
            max_tokens=self.max_new_tokens,
            n=num_return_sequences
        )

        start_time = time.time()
        try:
            output = self.llm.generate(conversation, sampling_params)
            elapsed_time = time.time() - start_time

            responses = [completion.text for completion in output[0].outputs]

            total_tokens = sum(len(response.split()) for response in responses)

        except Exception as e:
            logging.error(f"Error during generation: {e}")
            responses = [""] * num_return_sequences
            total_tokens = 0
            elapsed_time = self.timeout_seconds

        return responses, total_tokens, elapsed_time

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
