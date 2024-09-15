import llama3_chat as chat
from storage import FileStore
import os
import argparse
import pandas as pd
import numpy as np
from evaluation import pass_at_k

if __name__=="__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-g', '--generations', type=int, required=True)
    parser.add_argument('-c', '--compiler', type=str, required=True)
    args = parser.parse_args()

    df = pd.DataFrame(columns=["temperature", 
                                "top_p", 
                                "pass rate",
                                "pass@1",
                                "pass@5",
                                "pass@10",
                                "pass@25",
                                "compile fails",
                                "sim fails",
                                "timeout fails",
                                "report fails",
                                "decode fails",
                                "compile fail rate",
                                "sim fail rate",
                                "timeout fail rate",
                                "report fail rate",
                                "decode fail rate",
                                "max total coverage",
                                "average total coverage",
    ])
    
    # Read the prompt
    prompt1_file = open('method2_stage1_prompt.txt', 'r')
    prompt1 = prompt1_file.read()
    prompt1_file.close()

    prompt2_file = open('method2_stage2_prompt.txt', 'r')
    prompt2 = prompt2_file.read()
    prompt2_file.close()

    # Create a directory to store generations
    store = FileStore('./generations')
    chat.load_model()

    temperature = 0.6
    top_p=0.9

    total_pass = 0
    total_fail = 0
    num_compile_fail = 0 # A high number of compile failures means its is generating too many test benches that cannot compile
    num_sim_fail = 0 # A high number fo sim failures means its generating too many test benches that cannot simulate
    num_timeout_fail = 0 # A high number of timeout failures means you might want to increase the timeout
    num_report_fail = 0 # A high number of report failures might imply some other structural error
    num_decode_fail = 0 # A high number of decode failures means the llm is generating unfinished test benches

    max_cov = 0
    sum_cov_of_success = 0

    runs = args.generations

    for i in range(0,runs):
        # Run generations
        # Initialize conversation history with system message
        print(f"\n\nRun {i}")
        conversation = [
            {"role": "system", "content": "You are a verification engineering assistant tasked with generating test benches that meet a coverage requirement of 100% statement coverage."}
        ]
        conversation.append({"role":"user", "content":prompt1})

        response = chat.generate_response(conversation_history=conversation)
        print(response)

        conversation.append({'role':"assistant", "content":response})
        conversation.append({"role":"user", "content":prompt2})

        response = chat.generate_response(conversation_history=conversation)
        response = chat.convert_json_response_to_dict(response)
        print(response)

        cov = chat.get_coverage(args.compiler, response[0]['test bench'], f'./sha12/design/tb_llm_m2_{i}.v', storage=store)
        if cov.success:
            print(f"Passed!\n{cov.error_message}")
            total_pass = total_pass + 1
            sum_cov_of_success = sum_cov_of_success + int(cov.total_coverage)
            if int(cov.total_coverage) > max_cov:
                max_cov = int(cov.total_coverage)
        else:
            print(f"Failed!\n{cov.error_message}")
            total_fail = total_fail + 1
            if cov.error_code == 1:
                num_compile_fail = num_compile_fail + 1
            elif cov.error_code == 2:
                num_sim_fail = num_sim_fail + 1
            elif cov.error_code == 3:
                num_timeout_fail = num_timeout_fail + 1
            elif cov.error_code == 4:
                num_report_fail = num_report_fail + 1
            else:
                num_decode_fail = num_decode_fail + 1

        df = pd.DataFrame([{"temperature": temperature, 
                            "top_p": top_p, 
                            "pass rate": total_pass / (total_pass + total_fail),
                            "pass@1": pass_at_k((total_pass + total_fail), total_pass, 1),
                            "pass@5": pass_at_k((total_pass + total_fail), total_pass, 5),
                            "pass@10": pass_at_k((total_pass + total_fail), total_pass, 10),
                            "pass@25": pass_at_k((total_pass + total_fail), total_pass, 25),
                            "compile fails": num_compile_fail,
                            "sim fails": num_sim_fail,
                            "timeout fails": num_timeout_fail,
                            "report fails": num_report_fail,
                            "decode fails": num_decode_fail,
                            "compile fail rate": num_compile_fail / (total_pass + total_fail),
                            "sim fail rate": num_sim_fail / (total_pass + total_fail),
                            "timeout fail rate": num_timeout_fail / (total_pass + total_fail),
                            "report fail rate": num_report_fail / (total_pass + total_fail),
                            "decode fail rate": num_decode_fail / (total_fail + total_pass),
                            "max total coverage": max_cov,
                            "average total coverage": sum_cov_of_success / total_pass,
        }])
        print(df)
    
    df = pd.DataFrame([{"temperature": temperature, 
                        "top_p": top_p, 
                        "pass rate": total_pass / (total_pass + total_fail),
                        "pass@1": pass_at_k((total_pass + total_fail), total_pass, 1),
                        "pass@5": pass_at_k((total_pass + total_fail), total_pass, 5),
                        "pass@10": pass_at_k((total_pass + total_fail), total_pass, 10),
                        "pass@25": pass_at_k((total_pass + total_fail), total_pass, 25),
                        "compile fails": num_compile_fail,
                        "sim fails": num_sim_fail,
                        "timeout fails": num_timeout_fail,
                        "report fails": num_report_fail,
                        "decode fails": num_decode_fail,
                        "compile fail rate": num_compile_fail / (total_pass + total_fail),
                        "sim fail rate": num_sim_fail / (total_pass + total_fail),
                        "timeout fail rate": num_timeout_fail / (total_pass + total_fail),
                        "report fail rate": num_report_fail / (total_pass + total_fail),
                        "decode fail rate": num_decode_fail / (total_fail + total_pass),
                        "max total coverage": max_cov,
                        "average total coverage": sum_cov_of_success / total_pass,
    }])
    
    df.to_csv('methodology2.csv')