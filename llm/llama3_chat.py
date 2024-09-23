from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import os
from datetime import datetime
import json
import questasim as qs
from storage import FileStore
import re
from environment import Environment

# Set the cache location for the model
os.environ['HUGGINGFACE_HUB_CACHE'] = "/scratch/slowe8/.cache/"

def load_model():
    # Set the cache location for the model
    os.environ['HUGGINGFACE_HUB_CACHE'] = "/scratch/slowe8/.cache/"

    # Define the model ID and load the tokenizer and model
    global model_id
    global tokenizer
    global model
    model_id = "meta-llama/Meta-Llama-3.1-70B-Instruct"
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )

# Function to generate a response from the LLM
def generate_response(conversation_history, max_new_tokens=10000, temperature=0.6, top_p=0.9) -> str:
    # Encode the conversation history
    input_ids = tokenizer.apply_chat_template(
        conversation_history,
        add_generation_prompt=True,
        return_tensors="pt"
    ).to(model.device)

    # Define terminators for the generated output
    terminators = [
        tokenizer.eos_token_id,
        tokenizer.convert_tokens_to_ids("<|eot_id|>")
    ]

    # Generate the response
    outputs = model.generate(
        input_ids,
        max_new_tokens=max_new_tokens,
        eos_token_id=terminators,
        do_sample=True,
        temperature=0.5,
        top_p=0.9,
    )

    # Decode and return the response
    response = outputs[0][input_ids.shape[-1]:]
    return tokenizer.decode(response, skip_special_tokens=True)

# Function to generate a response from the LLM in batch
# TODO: Test
def batch_generate(conversations, batch_size=10, max_new_tokens=10000, temperature=0.6, top_p=0.9) -> list:
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
def get_coverage(questa_dir: str, generated_response: str, tb_path: str, storage: FileStore = None) -> qs.CoverageResponse:
    if not generated_response:
        return qs.CoverageResponse(False, 5, "Empty test bench (JSON Decode Error)")

    # Write the generated testbench to a file
    with open(tb_path, "w+") as testbench_file:
        testbench_file.write(generated_response)

    # Run QuestaSim to get coverage
    # env = Environment(questa_dir)
    coverage_response = qs.run_questasim(questa_dir, tb_path, "questasim.log")

    # Move test bench file to storage
    storage.move(tb_path)

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

