# This function returns the initial prompt used for generating a test bench
def m1_prompt(design_specification: str, module_header: str) -> str:
    template = f'''Generate a Verilog testbench named tb_llm for the following design specification. \
                The test bench should meet the statement coverage goal of 100%. \
                Generate only the Verilog testbench and no additional words. \
                Make sure you are ONLY using Verilog syntax and features, and not SystemVerilog such as for loops.\n\
                Module header:\n{module_header}\n
                Design Specification:\n{design_specification}
                Provide the generated testbench in a JSON format as shown below. You should put the generated test bench into the "test bench" tag and any additonal comments into the "comments" tag.\n
                ''' + '''
                Example output:\n\{\"test bench\": \"module tb_llm;\n// Generated test bench code\n$finish\nendmodule\n\",\"comments\": \" // Any additonal comments here \"}
                '''

# This function returns two prompts
# The first prompt should be used to generate the verification plan
# The second prompt should be used to generate the test bench after the verification plan is generated
# The second prompt assumes that conversation histroy is being provided to the LLM in addition to the second prompt
def m2_prompts(design_specification: str, module_header: str) -> (str, str):
    pass