# import sys
# sys.path.append('/home/asbabbit/llm_verif_dataset/llm_src')
# import xml.etree.ElementTree as ET

from src.questasim import CoverageResponse
import os
import pathlib
from random import randint
# from environment import Environment

# This function returns the initial prompt used for generating a test bench
def m1_prompt(design_specification: str, module_header: str) -> str:
    return f'''Generate a Verilog testbench named tb_llm for the following design specification.
The test bench should meet the statement coverage goal of 100%.
Generate only the Verilog testbench and no additional words.
Make sure you are ONLY using Verilog syntax and features, and not SystemVerilog such as for loops and asserts.\n
Module header:\n{module_header}\n
Design Specification:\n{design_specification}\n
Provide the generated testbench in a JSON format as shown below. You should put the generated test bench into the "test bench" tag and any additonal comments into the "comments" tag. Keep the test bench less than 500 lines.\n
''' + '''Example output:
{
	"test bench": "
		module tb_llm;

			// Clock logic

			initial
			begin
				// Generted test cases
			$finish
			end
		endmodule
	",
	"comments": " // Any additonal comments here "
}
'''

def m2_prompt1(design_specification: str, module_header: str) -> str:
	p1 = f'''We are going to use a 2 stage process to generate a Verilog test bench for a Verilog design. 
Right now we are in the first stage. 
Generate a verification plan with test scenarios that will achieve full statement coverage of design described by the following design specification and module header. 
Module header:\n{module_header}\n
Design specification:\n{design_specification}
'''

	return p1

# This function returns two prompts
# The first prompt should be used to generate the verification plan
# The second prompt should be used to generate the test bench after the verification plan is generated
# The second prompt assumes that conversation histroy is being provided to the LLM in addition to the second prompt
def m2_prompts(design_specification: str, module_header: str) -> tuple[str, str]:
    p1 = f'''We are going to use a 2 stage process to generate a Verilog test bench for a Verilog design. 
Right now we are in the first stage. 
Generate a verification plan with test scenarios that will achieve full statement coverage of design described by the following design specification and module header.
Module header:\n{module_header}\n
Design specification:\n{design_specification}
'''
    p2 = '''Now we are in the second stage of the verification process. Generate a Verilog testbench for the module using the module header, specification, and verification plan.
Provide the generated testbench in a JSON format as shown below. You should put the generated test bench into the "test bench" tag and any additonal comments into the "comments" tag. Keep the test bench less than 500 lines.
Example output:
{
	"test bench": "
		module tb_llm;

			// Clock logic

			initial
			begin
				// Generted test cases
			$finish
			end
		endmodule
	",
	"comments": " // Any additonal comments here "
}
'''
    return (p1, p2)

def m3_prompt_wo_coverage() -> str:
	return '''The generated testbench did not meet coverage goals. Adjust the test bench to increase the coverage by adding more stimulus or exploring more possible edge cases. Make sure you are exercising the full range of inputs for each port. Make sure you are explicitly exploring error cases. You are able to reset the design under test if needed. Provide the generated testbench in a JSON format as shown below. You should put the generated test bench into the \"test bench\" tag and any additonal comments into the \"comments\" tag. Keep the test bench less than 500 lines.\n
Example output:
{
	"test bench": "
		module tb_llm;

			// Clock logic

			initial
			begin
				// Generted test cases
			$finish
			end
		endmodule
	",
	"comments": " // Any additonal comments here "
}
'''


def error_prompt(error_code: int, error_message: str) -> str:

	# Handle error responses from QuestaSim
	if error_code == 1:
		return f"The generated test bench failed to compile. Use the following error message to fix the errors. Use the same JSON format for the new testbench. Error Message:\n{error_message}\nProvide the generated testbench in a JSON format as shown below. You should put the generated test bench into the \"test bench\" tag and any additonal comments into the \"comments\" tag. Keep the test bench less than 500 lines.\n" + '''Example output:
{
	"test bench": "
		module tb_llm;

			// Clock logic

			initial
			begin
				// Generted test cases
			$finish
			end
		endmodule
	",
	"comments": " // Any additonal comments here "
}
'''
	elif error_code == 2:
		return f"The generated test bench failed to simulate. Use the following error message to fix the errors Use the same JSON format for the new testbench. Error Message:\n{error_message}\nProvide the generated testbench in a JSON format as shown below. You should put the generated test bench into the \"test bench\" tag and any additonal comments into the \"comments\" tag. Keep the test bench less than 500 lines.\n" + '''Example output:
{
	"test bench": "
		module tb_llm;

			// Clock logic

			initial
			begin
				// Generted test cases
			$finish
			end
		endmodule
	",
	"comments": " // Any additonal comments here "
}
'''
	elif error_code == 3:
		return f"The generated test bench took to long to simulate and timed out. Try to shorten the testbench. Use the same JSON format for the new testbench.Provide the generated testbench in a JSON format as shown below. You should put the generated test bench into the \"test bench\" tag and any additonal comments into the \"comments\" tag. Keep the test bench less than 500 lines.\n" + '''Example output:
{
	"test bench": "
		module tb_llm;

			// Clock logic

			initial
			begin
				// Generted test cases
			$finish
			end
		endmodule
	",
	"comments": " // Any additonal comments here "
}
'''
	elif error_code == 4:
		return f"You failed to generate a test bench. You either generated a terminating token too early, ran past the token limit, or took too long to generate. Try generating a shorter test bench with higher quality tests. Use the same JSON format for the new testbench. Provide the generated testbench in a JSON format as shown below. You should put the generated test bench into the \"test bench\" tag and any additonal comments into the \"comments\" tag. Keep the test bench less than 500 lines.\n" + '''Example output:
{
	"test bench": "
		module tb_llm;

			// Clock logic

			initial
			begin
				// Generted test cases
			$finish
			end
		endmodule
	",
	"comments": " // Any additonal comments here "
}
'''
	elif error_code == 5:
		return "You did not add a $finish command to your test bench so I cannot simulate it. Please add the $finish command in the correct place in the test bench."

	return ""

# TODO: Create option for LLM to create new test cases instead of repeating itself
def m3_prompt(all_design_files: list[str], coverage: CoverageResponse) -> str:

	if coverage.error_code != 0:
		return error_prompt(coverage.error_code, coverage.error_message)

	# Parse the XML coverage report file and create a dictionary of files with their line misses
	formatted_coverage_report = ""
	missed_lines = {}
	for inst in coverage.coverage_list:
		filename = os.path.split(inst.path)[1]
		for stmt in inst.coverage_details:
			if stmt.get('hits') == '0':
				line = int(str(stmt.get('ln')))
				if filename not in missed_lines:
					missed_lines[filename] = {"lines": []}
				missed_lines[filename]["lines"].append(line)
	
		formatted_coverage_report += f"File: {os.path.split(inst.path)[1]}\tActive: {inst.coverage['active']}\tHits: {inst.coverage['hits']}\tPercent: {inst.coverage['percent']}\n"

	if not missed_lines:
		return "No missed lines left to fix"

	#TODO: There maybe accessing to null lists for lines key if file not used in coverage report
	# Select random file and line where there is a miss
	rand_file = all_design_files[randint(0, len(all_design_files)-1)]
	rand_filename = os.path.split(rand_file)[1]
	rand_line_index = missed_lines[rand_filename]["lines"][randint(0, len(missed_lines[rand_filename]["lines"]) - 1)]

	missed_line = ""
	all_design_content = ""
	lines_list = {}
	for file in all_design_files:
		filename = os.path.split(file)[1]
		with open(file, 'r') as f:
			lines = f.readlines()

		if rand_filename == filename and lines[rand_line_index] != '\n':
			lines[rand_line_index] = lines[rand_line_index].replace('\n', " // This is the line that was not covered\n")
			missed_line = lines[rand_line_index]

		lines_list[filename] = {"lines": lines}
		all_design_content = all_design_content + '\n\n' + filename + '\n' + ''.join(lines)
	


	return '''The test bench that you generated did not meet coverage goals. Use the following coverage data and context to generate a test bench that achieves better coverage:
''' + formatted_coverage_report + f'''
Try to target this coverage hole at line {rand_line_index} in the file {rand_filename}: {missed_line.strip()}
Please see if the targed coverage hole at line {rand_line_index} is inside an if or case statement and try to hit that condition
Listed below are the files for the whole design, use them as context to improve coverage.
{all_design_content}

There are three options for improving line coverage, choose one of these option:
1. Add another testcase to a previously generated testbench
2. Modify a testcase from a previously generated testbench
3. Generate a completely new testbench without previous generations as context

Generate a Verilog testbench named tb_llm for the following design specification.
The test bench should meet the statement coverage goal of 100%.
Generate only the Verilog testbench and no additional words.
Make sure you are ONLY using Verilog syntax and features, and not SystemVerilog such as for loops and asserts.\n
Provide the generated testbench in a JSON format as shown below. You should put the generated test bench into the "test bench" tag and any additonal comments into the "comments" tag. Keep the test bench less than 500 lines.\n
''' + '''Example output:
{
	"test bench": "
		module tb_llm;

			// Clock logic

			initial
			begin
				// Generted test cases
			$finish
			end
		endmodule
	",
	"comments": " // Any additonal comments here "
}
'''

def design_prompt(all_design_files: list[str]) -> str:

	base: str = "Here is the full design to give you more context about the logic of each module:\n\n"

	for file_path in all_design_files:
		with open(file_path, 'r') as f:
			base += f"{file_path}:\n{f.read()}\n\n"

	return base