from ctypes import ArgumentError
import requests
from llm_verif.simulator import Simulator, CoverageResponse
from llm_verif.modelchat import ModelChat
from llm_verif.storage import FileStore
import torch
from typing import Union, Any, Callable
from transformers import PreTrainedModel, PreTrainedTokenizer, AutoTokenizer
import logging
import os

class OllamaChat:
    def __init__(self, model_id: str, simulator: Simulator | None, do_sample: bool, temperature_function: str = "constant",
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
        self.model_id: str = model_id
        self.ollama_url = "http://localhost:11434/api/generate"

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
            self.model, self.tokenizer = self.load_model(self.model_id, seed=seed)
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

    def load_model(self, model_id, seed: Union[int, None] = None) -> tuple[Any, Any]:
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

        tokenizer: Any = AutoTokenizer.from_pretrained(model_id)
        model: Any = None

        return model, tokenizer # type: ignore

    def unload_model(self):
        """
        Unload the Llama model and tokenizer to free up memory.
        """
        del self.model

    def generate_response(self, conversation_history):
        """
        Sends a request to the Ollama API to generate a response
        """

        if not conversation_history:
            raise ArgumentError("Conversation history is required.")
        
        # Convert the conversation into one formatted prompt
        full_prompt = OllamaChat.format_conversation(conversation_history)

        payload = {
            "model": "llama3.1:70b",
            "prompt": full_prompt,
            "options": {
                "temperature": self.temperature,
                "top_p": self.top_p,
                "max_tokens": self.max_new_tokens
            }
        }

        response = requests.post(self.ollama_url, json=payload)
        response_json = response.json()

        if "respose" not in response_json:
            raise RuntimeError(f"Error from Ollama API: {response_json}")
        
        return response_json["response"], len(response_json["response"].split()), response_json.get("time", 0)

    @staticmethod
    def format_conversation(conversation_history):

        formatted_messages = []
        for message in conversation_history:
            role = message["role"].capitalize()
            content = message["content"]
            formatted_messages.append(f"{role}: {content}")

        return "\n\n".join(formatted_messages)
    
    def get_coverage(self, generated_response: str, tb_path: str, data_point: dict[str, str | list[str]] | None, storage: FileStore = None) -> CoverageResponse:
        if not generated_response:
            return CoverageResponse(False, 4, "Empty test bench (JSON Decode Error)")

        # Write the generated testbench to a file
        print(tb_path)
        with open(tb_path, "w+") as testbench_file:
            testbench_file.write(generated_response)

        # Run QuestaSim to get coverage
        # env = Environment(questa_dir)
        log_name = tb_path.split('.')[0]
        coverage_response = self.simulator.run_simulation_flow(tb_path=tb_path, data_point=data_point, log_name=log_name)

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