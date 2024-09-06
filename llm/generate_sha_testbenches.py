import llama3_chat as chat
from storage import FileStore
import os

if __name__=="__main__":
    
    # Read the prompt
    prompt_file = open('few_shot_prompt.txt', 'r')
    prompt = prompt_file.read()

    # Create a directory to store generations
    store = FileStore('./generations')

    for i in range(0,100):
        # Run generations
        # Initialize conversation history with system message
        conversation = [
            {"role": "system", "content": "You are a verification engineering assistant tasked with generating test benches that meet a coverage requirement of 100% statement coverage."}
        ]
        conversation.append({"role":"user", "content":prompt})

        chat.load_model()
        response = chat.generate_response(conversation_history=conversation)
        print(response)
        response = chat.convert_json_response_to_dict(response)

        cov = chat.get_coverage(response[0]['test bench'], './sha12/design')
        if cov != "":
            print("Passed!")
        else:
            print("Failed!")
