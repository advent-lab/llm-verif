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
from math import exp, log10
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Union
from vllm import LLM, SamplingParams 
from pathlib import Path
import re

logging.basicConfig(level=logging.INFO)

# Set cache location for model
if not os.path.isdir(f"/scratch/{os.environ['USER']}/.cache/"):
    os.mkdir(f"/scratch/{os.environ['USER']}/.cache/")
os.environ['HUGGINGFACE_HUB_CACHE'] = f"/scratch/{os.environ['USER']}/.cache/"

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
        self.simulator: Simulator | Any
        self.environment: Environment | Any = environment
        self.model: Any
        self.tokenizer: Any
        self.do_sample: bool
        self.temperature_function: Callable[[int], float]
        self.temperature: float
        self.top_p: float
        self.max_new_tokens: int
        self.timeout_seconds: float

        self.simulator = simulator
        if not skip_load:
            self.llm, self.tokenizer = self.load_model(seed=seed)
        self.do_sample = do_sample

        if temperature_function == "constant":
            self.temperature_function = lambda _: temperature
        elif temperature_function == "logarithmic":
            self.temperature_function = LlamaChat.logarithmic_temperature
        elif temperature_function == "capped_sigmoid":
            self.temperature_function = LlamaChat.capped_sigmoid_temperature
        else:
            raise ValueError(f"Unknown temperature function: {temperature_function}")

        self.top_p = top_p
        self.max_new_tokens = max_new_tokens
        self.timeout_seconds = timeout_seconds

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

        os.environ['HUGGINGFACE_HUB_CACHE'] = f"/scratch/{os.environ['USER']}/.cache/"
        os.environ['HF_HOME'] = f"/scratch/{os.environ['USER']}/.cache/"
        # Base model cache directory

        cache_dir = Path(f"/scratch/{os.environ['USER']}/.cache/{self.environment.model_id}/snapshots")
        
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
                quantization="bitsandbytes",
                load_format="bitsandbytes",
                #tensor_parallel_size=num_gpus,
                gpu_memory_utilization=0.98,
                max_model_len=32766
            )
        else:
             # Load vLLM model
            llm = LLM(
                model=model_id,
                tensor_parallel_size=num_gpus,
                gpu_memory_utilization=0.98,
                max_model_len=32766
            )

        return llm, llm.get_tokenizer()

    def unload_model(self):
        """
        Unload the Llama model and tokenizer to free up memory.
        """
        del self.model

    @staticmethod
    def format_conversations(conversation: list[dict[str, str]]) -> str:
        formatted_messages = []
        for message in conversation:
            role = message['role'].capitalize()
            content = message["content"]
            formatted_messages.append(f"{role}: {content}")

        return "\n\n".join(formatted_messages)

    def generate_response(self, conversation_history: list[dict[str, str]], num_return_sequences=2) -> tuple[list[str], int, float]:
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
        self.temperature = self.temperature_function(len(conversation_history))

        formatted_conversation = LlamaChat.format_conversations(conversation_history)

        sampling_params = SamplingParams(
            temperature=self.temperature if self.do_sample else None,
            top_p=self.top_p if self.do_sample else None,
            max_tokens=self.max_new_tokens,
            n=num_return_sequences
        )

        start_time = time.time()
        try:
            output = self.llm.generate(formatted_conversation, sampling_params)
            elapsed_time = time.time() - start_time

            responses = [completion.text for completion in output[0].outputs]

            total_tokens = sum(len(response.split()) for response in responses)

        except Exception as e:
            logging.error(f"Error during generation: {e}")
            responses = [""] * num_return_sequences
            total_tokens = 0
            elapsed_time = self.timeout_seconds

        return responses, total_tokens, elapsed_time
    
    def generate_batch_responses(self, batch_conversations: list[list[dict[str, str]]], batch_size: int = 5):

        """
        Generates multiple responses for each input conversation in batch.

        Args:
            model: The LLM model.
            tokenizer: The tokenizer for the model.
            conversations (list of list of dict): Batch of conversations, where each conversation is a list of dicts.
            batch_size (int): Number of responses to generate per conversation.
            max_new_tokens (int): Max tokens to generate per response.
            temperature (float): Sampling temperature.
            top_p (float): Top-p sampling probability.

        Returns:
            tuple:
                - generated_responses (list of lists): A list where each item is a list of generated responses for each conversation.
                - total_tokens (int): Total tokens generated across all responses.
                - total_time (float): Time taken for generation in seconds.
        """

        # Apply chat template to each conversation
        formatted_inputs = [
            self.tokenizer.apply_chat_template(conv, add_generation_prompt=True, return_tensors="pt")
            for conv in batch_conversations
        ]

        # Pad and create batch input tensors
        inputs = torch.nn.utils.rnn.pad_sequence(formatted_inputs, batch_first=True, padding_value=self.tokenizer.pad_token_id) # type: ignore
        inputs = inputs.to(self.model.device)

        # Start timing
        start_time = time.time()

        # Generate responses in batch with num_return_sequences
        with torch.no_grad():
            outputs = self.model.generate(
                inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=True,
                temperature=self.temperature,
                top_p=self.top_p,
                num_return_sequences=batch_size  # Generate 'batch_size' outputs per input conversation
            )

        # Measure time taken
        total_time = time.time() - start_time

        # Reshape output tensor to properly match batch_size and input batch
        num_inputs = len(batch_conversations)
        outputs = outputs.view(num_inputs, batch_size, -1)  # type: ignore # Shape: (num_inputs, batch_size, sequence_length)

        # Decode outputs
        generated_responses = [
            self.tokenizer.batch_decode(batch_outputs, skip_special_tokens=True) for batch_outputs in outputs
        ]

        # Calculate total number of tokens generated
        total_tokens = sum(output.shape[-1] for output in outputs.flatten(start_dim=1))

        return generated_responses, total_tokens, total_time
    
    def log_conversation(self, conversation_update: list[dict[str, str]], log_file: str):
        """
        Log the conversation history to a specified file.

        Args:
            conversation_update (list[dict]): A list of message dictionaries to log.
            log_file (str): Path to the log file.

        Returns:
            None
        """
        with open(log_file, 'a') as f:
            f.write(f"--- Conversation Log: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            for message in conversation_update:
                f.write(f"{message['role'].capitalize()}: {message['content']}\n")
            f.write("\n")

    # Function to collect multi-line input from the user
    def get_multiline_input(self, prompt: str ="Enter your message (end with 'END' on a new line):"):
        print(prompt)
        lines: list[str] = []
        while True:
            line = input()
            if line.strip().upper() == "END":
                break
            lines.append(line)
        return "\n".join(lines)

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


    # TODO: Create call to QuestaSim to get coverage
    def get_coverage(self, generated_response: str, tb_path: str, data_point: dict[str, str | list[str]] | None, storage: FileStore = None, batch: int = 0) -> CoverageResponse:
        if not generated_response:
            return CoverageResponse(False, 4, "Empty test bench (JSON Decode Error)")

        # Write the generated testbench to a file
        print(tb_path)
        with open(tb_path, "w+") as testbench_file:
            testbench_file.write(generated_response)

        # Run QuestaSim to get coverage
        # env = Environment(questa_dir)
        log_name = tb_path.split('.')[0] 
        coverage_response = self.simulator.run_sim(tb_path=tb_path, data_point=data_point, log_name=log_name)

        # Move test bench file to storage
        if storage:
            storage.move(tb_path)
            storage.move(f'{log_name}_compile.log')
            storage.move(f'{log_name}_sim.log')
            storage.move(f'{log_name}.ucdb')
            storage.move(f'{log_name}_report.txt')
        

        return coverage_response

    def get_merge_coverage(self, run: int):
        self.simulator.merge_coverage()

    def limit_conversation(self, conversation, context_window=32766, stack_pointer: int = -1, design_prompt_idx: int = -1):
        """
        Trims the conversation while maintaining key indices.

        Args:
            conversation (list[dict]): Conversation history.
            context_window (int): Max token limit.
            stack_pointer (int | None): Index of last valid user message.
            design_prompt_idx (int | None): Index of design prompt message.

        Returns:
            tuple: (trimmed_conversation, updated_stack_pointer, updated_design_prompt_idx)
        """

        if not conversation or not isinstance(conversation, list):
            print("Error: Conversation must be a non-empty list of messages.")
            return conversation, stack_pointer, design_prompt_idx

        # Calculate current token count
        current_token_count = sum(len(self.tokenizer.encode(msg["content"])) for msg in conversation)
        max_token_count = context_window - self.max_new_tokens

        # Trim conversation while keeping key messages
        while current_token_count > max_token_count and len(conversation) > 2:
            removed_message = conversation.pop(1)  # Remove from front (preserve system message)

            # Adjust pointers
            if stack_pointer > 1:
                stack_pointer -= 1
            if design_prompt_idx > 1:
                design_prompt_idx -= 1

            # Recalculate token count after removal
            current_token_count = sum(len(self.tokenizer.encode(msg["content"])) for msg in conversation)

        # Handle missing stack pointer
        if stack_pointer < 0:
            # Find the first remaining user message
            stack_pointer = next((i for i, msg in enumerate(conversation) if msg["role"] == "user"), -1)

        # Handle missing design prompt
        if design_prompt_idx < 0:
            if stack_pointer >= 0:
                print("Warning: Design prompt was lost! Re-inserting before stack pointer.")
                conversation.insert(stack_pointer, {"role": "user", "content": design_prompt(self.environment.all_design_file_paths)})
                design_prompt_idx = stack_pointer  # Now design prompt is at this index
                stack_pointer += 1  # Adjust stack pointer to stay after design prompt

        return conversation, stack_pointer, design_prompt_idx

    def parallel_get_coverage(self, responses: str, test_benches: list[str], data_points: list[dict], store: FileStore = None) -> list[CoverageResponse]:
        """
        Run coverage simulations in parallel for multiple test benches.

        Args:
            test_benches (list[str]): List of test bench file paths.
            data_points (list[dict]): List of data points for each simulation.

        Returns:
            list[CoverageResponse]: List of coverage responses.
        """
        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(self.get_coverage, t[0], t[1], t[2], store, i)
                for i, t in enumerate(zip(responses, test_benches, data_points))
            ]
            return [future.result() for future in futures]


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
