from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from accelerate import infer_auto_device_map
import torch
import os
import json
from storage import FileStore
import questasim as qs
import re
from environment import Environment
import time

# Set cache location for model
if not os.path.isdir(f"/scratch/{os.environ['USER']}/.cache/"):
    os.mkdir(f"/scratch/{os.environ['USER']}/.cache/")
os.environ['HUGGINGFACE_HUB_CACHE'] = f"/scratch/{os.environ['USER']}/.cache/"

def load_model() -> AutoTokenizer:
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

    global tokenizer
    global model
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
    
    return tokenizer

# Generate a response from LLM with memory management
def generate_response(conversation_history, max_new_tokens=8192, temperature=0.3, top_p=0.7, timeout_seconds=1200) -> (str, int, float):
    input_ids = tokenizer.apply_chat_template(
        conversation_history,
        add_generation_prompt=True,
        return_tensors="pt"
    ).to(model.device)

    terminators = [tokenizer.convert_tokens_to_ids("<|eot_id|>")]

    # Start tracking time
    start_time = time.time()
    response = None

    try:
        with torch.no_grad():
            outputs = model.generate(
                input_ids,
                max_new_tokens=max_new_tokens,
                eos_token_id=terminators,
                do_sample=True,
                temperature=temperature,
                top_p=top_p,
                stopping_criteria=[lambda ids, scores: time.time() - start_time > timeout_seconds]
            )
        
        elapsed_time = time.time() - start_time

        # Decode the response and calculate token count
        response_ids = outputs[0][input_ids.shape[-1]:]
        response = tokenizer.decode(response_ids, skip_special_tokens=True)
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
def batch_generate(conversations, batch_size=10, max_new_tokens=10000, temperature=0.3, top_p=0.7) -> list:
    generated_testbenches = []
    
    for i in range(0, len(conversations), batch_size):
        batch_conversations = conversations[i:i+batch_size]
        for conversation in batch_conversations:
            try:
                # Prepare the input for Llama3.1
                input_ids = tokenizer.apply_chat_template(
                    conversation,
                    add_generation_prompt=True,
                    return_tensors="pt"
                ).to(model.device)

                terminators = [
                    tokenizer.eos_token_id,
                    tokenizer.convert_tokens_to_ids("<|eot_id|>")
                ]

                with torch.no_grad():
                    outputs = model.generate(
                        input_ids,
                        max_new_tokens=max_new_tokens,
                        eos_token_id=terminators,
                        do_sample=True,
                        temperature=temperature,
                        top_p=top_p,
                    )

                testbench_code = tokenizer.decode(outputs, skip_special_tokens=True)
                generated_testbenches.append(testbench_code)
            except Exception as e:
                print(f"Error generating for conversation {conversation}: {str(e)}")
                generated_testbenches.append(f"Error for {conversation}")
    
    return generated_testbenches

# Function to log the conversation to a file
def log_conversation(conversation_update, log_file):
    with open(log_file, 'a') as f:
        f.write(f"--- Conversation Log: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        for message in conversation_update:
            f.write(f"{message['role'].capitalize()}: {message['content']}\n")
        f.write("\n")

# Function to collect multi-line input from the user
def get_multiline_input(prompt="Enter your message (end with 'END' on a new line):"):
    print(prompt)
    lines = []
    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        lines.append(line)
    return "\n".join(lines)

# Parse JSON Response from LLM to dict
def convert_json_response_to_dict(generated_response: str) -> tuple:

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
def get_coverage(environment: Environment, generated_response: str, tb_path: str, data_point: dict, storage: FileStore = None) -> qs.CoverageResponse:
    if not generated_response:
        return qs.CoverageResponse(False, 4, "Empty test bench (JSON Decode Error)")

    # Write the generated testbench to a file
    with open(tb_path, "w+") as testbench_file:
        testbench_file.write(generated_response)

    # Run QuestaSim to get coverage
    # env = Environment(questa_dir)
    log_name = tb_path.split('.')[0]
    coverage_response = qs.run_questasim(environment, tb_path=tb_path, data_point=data_point, log_name=log_name)

    # Move test bench file to storage
    if storage:
        storage.move(tb_path)
        storage.move(f'{log_name}_compile.log')
        storage.move(f'{log_name}_sim.log')
        storage.move(f'{log_name}.ucdb')
        storage.move(f'{log_name}_report.txt')
    

    return coverage_response

# TODO: Implement parallel coverage runs
def parallel_get_coverage():
    pass

if __name__=="__main__":
    # Initialize model
    load_model()
    
    # Initialize conversation history with system message
    conversation_history = [
        {"role": "system", "content": "You are a verification engineering assistant tasked with generating test benches that meet a coverage requirement of 100% statement coverage."}
    ]

    # Specify the log file name
    log_file = f"conversation_log{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    print("Welcome to the Verilog Testbench Generator!")
    print("You can interact with the LLM continuously. Type 'exit' to quit.\n")

    # Main interactive loop
    while True:

        # Start a record of this prompt and response
        conversation_update = []

        # Get the multi-line user input
        user_input = get_multiline_input()

        if user_input.lower() == 'exit':
            print("Exiting the conversation.")
            log_conversation(conversation_history, log_file)
            break

        # Add the user's input to the conversation history
        conversation_update.append({"role": "user", "content": user_input})
        conversation_history.append({"role": "user", "content": user_input})

        # Generate a response from the LLM
        verilog_testbench = generate_response(conversation_history)

        # Print the generated response
        print("\nGenerated Verilog Testbench or Response:\n")
        print(verilog_testbench)

        # Add the model's response to the conversation history
        conversation_update.append({"role": "assistant", "content": verilog_testbench})
        conversation_history.append({"role": "assistant", "content": verilog_testbench})


        # Log the updated conversation to the log file
        log_conversation(conversation_update, log_file)

        # Limit conversation memory to about 4000 tokens (estimate based on token count)
        current_token_count = sum(len(tokenizer.encode(msg["content"])) for msg in conversation_history)
        max_token_count = 125000
        while current_token_count > max_token_count:
            # Remove the oldest messages to maintain memory size
            conversation_history.pop(1)  # Assuming the first message is the system prompt, so we pop the second one
            current_token_count = sum(len(tokenizer.encode(msg["content"])) for msg in conversation_history)

