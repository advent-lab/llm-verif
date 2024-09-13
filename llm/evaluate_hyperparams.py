import llama3_chat as chat
from storage import FileStore
import os
import argparse
import pandas as pd
import numpy as np

if __name__=="__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--compiler')
    args = parser.parse_args()

    df = pd.DataFrame(columns=["temperature", "top_p", "pass rate"])
    
    # Read the prompt
    prompt_file = open('few_shot_prompt.txt', 'r')
    prompt = prompt_file.read()

    # Create a directory to store generations
    # store = FileStore('./generations')
    chat.load_model()

    for temperature in np.arange(0.1, 1.1, 0.1):
        for top_p in np.arange(0.1, 1.1, 0.1):
            num_pass = 0
            num_fail = 0
            for i in range(0,1):
                # Run generations
                # Initialize conversation history with system message
                print(f"\n\nRun {i}")
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
                    num_pass = num_pass + 1
                else:
                    print(f"Failed!\n{cov[1]}")
                    num_fail = num_fail + 1
            
            pass_rate = num_pass / (num_pass + num_fail)
            new_record = pd.DataFrame([{"temperature": str(temperature), "top_p": str(top_p), "pass rate": str(pass_rate)}])
            df = pd.concat([df, new_record], ignore_index=True)
            print(df)
    
    df.to_csv('hyperparams_eval.csv')

            
