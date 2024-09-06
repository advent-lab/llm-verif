import llama3_chat as chat
import os

if __name__ == "__main__":

    stringified_json = chat.convert_json_response_to_dict(open('json_ex.txt', 'r').read())

    reformatted_testbench = remove_indentation_from_string(stringified_json[0]['test bench'])

    with open('converted_tb.v', 'w+') as w:
        w.write(reformatted_testbench)
