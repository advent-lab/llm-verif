import llama3_chat as chat
import os

if __name__=="__main__":
    
    # Read the prompt
    prompt_file = open('few_shot_prompt.txt', 'r')
    prompt = prompt_file.read()

    # Create a directory to store generations
    if not os.path.isdir('./generations'):
        os.mkdir('./generations')

    # Run generations
    # Initialize conversation history with system message
    conversation = [
        {"role": "system", "content": "You are a verification engineering assistant tasked with generating test benches that meet a coverage requirement of 100% statement coverage."}
    ]
    conversation.append({"role":"user", "content":prompt})

    chat.load_model()
    response = chat.generate_response(conversation_history=conversation)
    print(response)
    print(chat.convert_json_reponse_to_dict(response))
