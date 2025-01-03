from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from accelerate import infer_auto_device_map
import torch
import os
import json
from src.storage import FileStore
import re
import time
from pathlib import Path
from src.dashboard import Dataset
from src.simulator import Simulator, CoverageResponse
from math import exp, log10

# Set cache location for model
if not os.path.isdir(f"/scratch/{os.environ['USER']}/.cache/"):
    os.mkdir(f"/scratch/{os.environ['USER']}/.cache/")
os.environ['HUGGINGFACE_HUB_CACHE'] = f"/scratch/{os.environ['USER']}/.cache/"

class LlamaChat():

    def __init__(self, simulator: Simulator, temperature: float, top_p: float, max_new_tokens: int, timeout_seconds: int):

        self.simulator = simulator

        self.model, self.tokenizer = self.load_model()

        self.temperature = temperature
        self.top_p = top_p
        self.max_new_tokens = max_new_tokens
        self.timeout_seconds= timeout_seconds

    def load_model(self) -> AutoTokenizer:
        os.environ['HUGGINGFACE_HUB_CACHE'] = f"/scratch/{os.environ['USER']}/.cache/"

        # Model and tokenizer setup with quantization
        model_id = "meta-llama/Meta-Llama-3.1-70B-Instruct"
        compute_dtype = getattr(torch, "float16")

        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=compute_dtype,
            bnb_4bit_use_double_quant=False,
        )

        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            quantization_config=bnb_config,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )

        # Optional manual device map
        device_map = infer_auto_device_map(model)
        with open("./device_map.json", 'w+') as j:
            json.dump(device_map, j)
        
        return model, tokenizer

    # Generate a response from LLM with memory management
    def generate_response(self, conversation_history) -> (str, int, float):

        temperature = LlamaChat.logarithmic_temperature(len(conversation_history))

        input_ids = self.tokenizer.apply_chat_template(
            conversation_history,
            add_generation_prompt=True,
            return_tensors="pt"
        ).to(self.model.device)

        terminators = [self.tokenizer.convert_tokens_to_ids("<|eot_id|>")]

        # Start tracking time
        start_time = time.time()
        response = None

        try:
            with torch.no_grad():
                outputs = self.model.generate(
                    input_ids,
                    max_new_tokens=self.max_new_tokens,
                    eos_token_id=terminators,
                    do_sample=True,
                    temperature=temperature,
                    top_p=self.top_p,
                    stopping_criteria=[lambda ids, scores: time.time() - start_time > self.timeout_seconds]
                )
            
            elapsed_time = time.time() - start_time

            # Decode the response and calculate token count
            response_ids = outputs[0][input_ids.shape[-1]:]
            response = self.tokenizer.decode(response_ids, skip_special_tokens=True)
            token_count = len(response_ids)

        except Exception as e:
            print("Generation timed out or encountered an error:", e)
            elapsed_time = timeout_seconds  # Set to max if timeout occurs
            token_count = 0

        # Free up memory post-generation
        torch.cuda.empty_cache()

        return response, token_count, elapsed_time


    # Function to generate a response from the LLM in batch
    # TODO: Test
    def batch_generate(self, conversations, batch_size=10, max_new_tokens=10000, temperature=0.3, top_p=0.7) -> list:
        generated_testbenches = []
        
        for i in range(0, len(conversations), batch_size):
            batch_conversations = conversations[i:i+batch_size]
            for conversation in batch_conversations:
                try:
                    # Prepare the input for Llama3.1
                    input_ids = self.tokenizer.apply_chat_template(
                        conversation,
                        add_generation_prompt=True,
                        return_tensors="pt"
                    ).to(self.model.device)

                    terminators = [
                        self.tokenizer.eos_token_id,
                        self.tokenizer.convert_tokens_to_ids("<|eot_id|>")
                    ]

                    with torch.no_grad():
                        outputs = self.model.generate(
                            input_ids,
                            max_new_tokens=max_new_tokens,
                            eos_token_id=terminators,
                            do_sample=True,
                            temperature=temperature,
                            top_p=top_p,
                        )

                    testbench_code = self.tokenizer.decode(outputs, skip_special_tokens=True)
                    generated_testbenches.append(testbench_code)
                except Exception as e:
                    print(f"Error generating for conversation {conversation}: {str(e)}")
                    generated_testbenches.append(f"Error for {conversation}")
        
        return generated_testbenches

    # Function to log the conversation to a file
    def log_conversation(self, conversation_update, log_file):
        with open(log_file, 'a') as f:
            f.write(f"--- Conversation Log: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            for message in conversation_update:
                f.write(f"{message['role'].capitalize()}: {message['content']}\n")
            f.write("\n")

    # Function to collect multi-line input from the user
    def get_multiline_input(self, prompt="Enter your message (end with 'END' on a new line):"):
        print(prompt)
        lines = []
        while True:
            line = input()
            if line.strip().upper() == "END":
                break
            lines.append(line)
        return "\n".join(lines)

    # Parse JSON Response from LLM to dict
    @classmethod
    def convert_json_response_to_dict(cls, generated_response: str) -> tuple:

        # If the response is empty or None, return an error
        if not generated_response:
            print(f"GPU timeout")
            return ({"test bench": ""}, 0)
        
        # Find the first and last JSON curly braces
        first_pos = generated_response.find('{')
        if first_pos != -1:
            generated_response = generated_response[first_pos:]
        
        last_pos = generated_response.rfind('}')
        if last_pos != -1:
            generated_response = generated_response[:last_pos + 1]

        try:
            # Parse JSON
            decoder = json.JSONDecoder(strict=False)
            parsed_response = decoder.raw_decode(generated_response)
        except json.JSONDecodeError as e:
            print(f"JSONDecodeError: {e}")
            return ({"test bench":""}, 0)

        return parsed_response

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

    def limit_conversation(self, conversation) -> dict[str, str]:
        # Limit conversation memory to about 8196 tokens (estimate based on token count)
        current_token_count = sum(len(self.tokenizer.encode(msg["content"])) for msg in conversation)
        max_token_count = 128000 - self.max_new_tokens
        while current_token_count > max_token_count:
            # Remove the oldest messages to maintain memory size
            conversation.pop(1)  # Assuming the first message is the system prompt, so we pop the second one
            current_token_count = sum(len(self.tokenizer.encode(msg["content"])) for msg in conversation)

        return conversation

    # TODO: Implement parallel coverage runs
    def parallel_get_coverage():
        pass

    # Returns a temperature for a given number of messages in a conversation
    @classmethod
    def capped_sigmoid_temperature(cls, n: int, T_start: float = 0.2, T_end: float = 0.8, N: int = 9, k: float = 0.9) -> float:
        # Ensure the temperature does not exceed T_end
        T = T_start + (T_end - T_start) / (1 + exp(-k * ((n - N) / 2)))
        return min(T, T_end)

    @classmethod
    def logarithmic_temperature(cls, n: int, T_start: float = 0.2, T_end: float = 0.8, N: int = 26, k: float = 0.9) -> float:
        T = T_start + (T_end - T_start)(log10(n + 1) / log10(N + 1))
        return min(T, T_end)