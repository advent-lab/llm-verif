import llama3_chat as chat
from storage import FileStore
import os
import argparse

if __name__=="__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--compiler')
    args = parser.parse_args()
    
    # Read the prompt
    prompt_file = open('few_shot_prompt.txt', 'r')
    prompt = prompt_file.read()

    # Create a directory to store generations
    store = FileStore('./generations')
    chat.load_model()

    for i in range(0,100):
        # Run generations
        # Initialize conversation history with system message
        conversation = [
            {"role": "system", "content": "You are a verification engineering assistant tasked with generating test benches that meet a coverage requirement of 100% statement coverage."}
        ]
        conversation.append({"role":"user", "content":prompt})

        
        response = chat.generate_response(conversation_history=conversation)
        response = chat.convert_json_response_to_dict(response)
        print(response)

        cov = chat.get_coverage(args.compiler, response[0]['test bench'], './sha12/design')
        if cov[0]:
            print(f"Passed!\n{cov[1]}")
        else:
            print(f"Failed!\n{cov[1]}")
