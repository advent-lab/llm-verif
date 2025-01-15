from datetime import datetime
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

logging.basicConfig(level=logging.INFO)

# Set cache location for model
if not os.path.isdir(f"/scratch/{os.environ['USER']}/.cache/"):
    os.mkdir(f"/scratch/{os.environ['USER']}/.cache/")
os.environ['HUGGINGFACE_HUB_CACHE'] = f"/scratch/{os.environ['USER']}/.cache/"

class LlamaChat:
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

    def __init__(self, simulator: Simulator | None, do_sample: bool, temperature_function: str = "constant",
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
        self.model: PreTrainedModel | Any
        self.tokenizer: PreTrainedTokenizer | Any
        self.do_sample: bool
        self.temperature_function: Callable[[int], float]
        self.temperature: float
        self.top_p: float
        self.max_new_tokens: int
        self.timeout_seconds: int

        self.simulator = simulator
        if not skip_load:
            self.model, self.tokenizer = self.load_model(seed=seed)
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

    def load_model(self, seed: Union[int, None] = None) -> tuple[PreTrainedModel, PreTrainedTokenizer]:
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

        model_id = "meta-llama/Meta-Llama-3.1-70B-Instruct"
        compute_dtype = getattr(torch, "float16")

        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=compute_dtype,
            bnb_4bit_use_double_quant=False,
        )

        tokenizer: PreTrainedTokenizer = AutoTokenizer.from_pretrained(model_id) # type: ignore
        model: PreTrainedModel = AutoModelForCausalLM.from_pretrained( # type: ignore
            model_id,
            quantization_config=bnb_config,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )

        # Save device map for debugging
        device_map = infer_auto_device_map(model) # type: ignore
        with open("./device_map.json", 'w+') as j:
            json.dump(device_map, j)

        return model, tokenizer # type: ignore

    def generate_response(self, conversation_history: list[dict[str, str]]) -> tuple[str, int, float]:
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
        if not conversation_history:
            raise ValueError("Conversation history is required.")

        # Evaluate new temperature based on temperautre function
        self.temperature = self.temperature_function(len(conversation_history))

        input_ids = self.tokenizer.apply_chat_template( # type: ignore
            conversation_history,
            add_generation_prompt=True,
            return_tensors="pt"
        ).to(self.model.device) # type: ignore

        terminators: list[int | list[int]] = [self.tokenizer.convert_tokens_to_ids("<|eot_id|>")]

        start_time = time.time()
        try:
            with torch.no_grad():
                outputs = self.model.generate( # type: ignore
                    input_ids, # type: ignore
                    max_new_tokens=self.max_new_tokens,
                    eos_token_id=terminators,
                    do_sample=self.do_sample,
                    temperature=self.temperature if self.do_sample else None,
                    top_p=self.top_p if self.do_sample else None,
                )

            elapsed_time = time.time() - start_time
            response_ids = outputs[0][input_ids.shape[-1]:] # type: ignore
            response = self.tokenizer.decode(response_ids, skip_special_tokens=True) # type: ignore
            token_count = len(response_ids) # type: ignore

        except Exception as e:
            logging.error(f"Error during generation: {e}")
            response = ""
            token_count = 0
            elapsed_time = self.timeout_seconds

        finally:
            torch.cuda.empty_cache()

        return response, token_count, elapsed_time
    
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
            return parsed_response, 0

        except json.JSONDecodeError as e:
            logging.error(f"JSONDecodeError: {e}. Response: {generated_response}")
            return {"error": "Malformed JSON content"}, 2

        except Exception as e:
            logging.error(f"Unexpected error during JSON parsing: {e}")
            return {"error": "Unexpected error"}, 3


    # TODO: Create call to QuestaSim to get coverage
    def get_coverage(self, generated_response: str, tb_path: str, data_point: dict, storage: FileStore = None) -> CoverageResponse:
        if not generated_response:
            return CoverageResponse(False, 4, "Empty test bench (JSON Decode Error)")

        # Write the generated testbench to a file
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

    def limit_conversation(self, conversation: list[dict], context_window: int = 128000) -> list[dict]:
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
        max_token_count = context_window - self.max_new_tokens

        # Trim conversation until within token limits
        while current_token_count > max_token_count and len(conversation) > 1:
            # Preserve the system message (index 0)
            conversation.pop(1)
            current_token_count = sum(len(self.tokenizer.encode(msg["content"])) for msg in conversation)

        if current_token_count > max_token_count:
            logging.warning("Conversation could not be fully limited within token limits.")

        return conversation


    def parallel_get_coverage(self, test_benches: list[str], data_points: list[dict]) -> list[CoverageResponse]:
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
                executor.submit(self.get_coverage, tb, dp)
                for tb, dp in zip(test_benches, data_points)
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
