# import sys
# sys.path.append('/home/asbabbit/llm_verif_dataset/llm_src')
# import xml.etree.ElementTree as ET

import re
from src.questasim import CoverageResponse
import os

def system_prompt(design_content: list[str] | None = None):

	design_message = ""
	if design_content:
		design_message = design_prompt(design_content)

	return f"""You are an expert Verilog verification assistant. You have expertise in writing high quality, high code coverage test bench for a wide variety of digital hardware designs.

Directions:

When generating a verification plan or test plan, You should generate a verification plan with test scenarios that will achieve full statement coverage of the design.
Your verification plan should cover as many valid and invalid sets of stimulus as possible to ensure you can reach the maximum coverage possible.

When generating a test bench:
There are three options for improving line coverage, choose one of these option:
1. Add another testcase to a previously generated testbench
2. Modify a testcase from a previously generated testbench
3. Generate a completely new testbench without previous generations as context

It is important to ensure that a generated test case is novel and does not duplicate existing patterns. Modify input sequences and edge cases where possible.

The test bench should meet the statement coverage goal of 100%.
Generate only the Verilog testbench and no additional words.
Make sure you are ONLY using Verilog syntax and features, and not SystemVerilog such as for loops and asserts.\n
Provide the generated testbench in a JSON format as shown below. You should put the generated test bench into the "test bench" tag and any additonal comments into the "comments" tag. Keep the test bench less than 500 lines. Ensure that there is only one testbench within the JSON formatted output.\n
Here are some additional guidelines for the test bench: \n
Please declare signals before using them. When instantiating the DUT, the signals connected to the input ports should be declared as a reg in the test bench. When instantiating the DUT, the signals connected to the output ports should be declared as a wire in the test bench. Also, do not connect module port to cross module references, such as dut.foo. \n
""" + '''Example response:
{
	"test bench": "
		module tb_llm;

			// Clock logic

			initial
			begin
				// Generted test cases
			$finish;
			end
		endmodule
	",
	"comments": " // Any additonal comments here "
}
''' # + f"\n{design_message}"

# This function returns the initial prompt used for generating a test bench
def m1_prompt(design_specification: str, module_header: str) -> str:
    return f'''Generate a Verilog testbench named tb_llm for the following design specification.
The test bench should meet the statement coverage goal of 100%.
Generate only the Verilog testbench and no additional words.
Make sure you are ONLY using Verilog syntax and features, and not SystemVerilog such as for loops and asserts.\n
Module header:\n{module_header}\n
Design Specification:\n{design_specification}\n
Provide the generated testbench in a JSON format as shown below. You should put the generated test bench into the "test bench" tag and any additonal comments into the "comments" tag. Keep the test bench less than 500 lines. Ensure that there is only one testbench within the JSON formatted output.\n
Here are some additional guidelines for the test bench: \n
Please declare signals before using them. When instantiating the DUT, the signals connected to the input ports should be declared as a reg in the test bench. When instantiating the DUT, the signals connected to the output ports should be declared as a wire in the test bench. Also, do not connect module port to cross module references, such as dut.foo. \n
''' + '''Example response:
{
	"test bench": "
		module tb_llm;

			// Clock logic

			initial
			begin
				// Generted test cases
			$finish;
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
Generate a verification plan in which you should create a list of features based on the specification. For each feature, identify test scenarios or stimulus that will 
achieve full statement coverage of the design described by the following design specification and module header.
Module header:\n{module_header}\n
Design specification:\n{design_specification}
'''
    p2 = '''Now we are in the second stage of the verification process. Generate a Verilog testbench for the module using the module header, specification, and verification plan.
Use the test scenarios or stimulus you identified in the verification plan to maximize the coverage of the design.
Provide the generated testbench in a JSON format as shown below. You should put the generated test bench into the "test bench" tag and any additonal comments into the "comments" tag. Keep the test bench less than 500 lines.
Here are some additional guidelines for the test bench: \n
Please declare signals before using them. When instantiating the DUT, the signals connected to the input ports should be declared as a reg in the test bench. When instantiating the DUT, the signals connected to the output ports should be declared as a wire in the test bench. Also, do not connect module port to cross module references, such as dut.foo. \n
Example response:
{
	"test bench": "
		module tb_llm;

			// Clock logic

			initial
			begin
				// Generted test cases
			$finish;
			end
		endmodule
	",
	"comments": " // Any additonal comments here "
}
'''
    return (p1, p2)

def m3_prompt_wo_coverage() -> str:
	return '''The generated testbench did not meet coverage goals. Adjust the test bench to increase the coverage by adding more stimulus or exploring more possible edge cases. Make sure you are exercising the full range of inputs for each port. Make sure you are explicitly exploring error cases. You are able to reset the design under test if needed. Provide the generated testbench in a JSON format as shown below. You should put the generated test bench into the \"test bench\" tag and any additonal comments into the \"comments\" tag. Keep the test bench less than 500 lines. Ensure that there is only one testbench within the JSON formatted output.\n
Here are some additional guidelines for the test bench: \n
Please declare signals before using them. When instantiating the DUT, the signals connected to the input ports should be declared as a reg in the test bench. When instantiating the DUT, the signals connected to the output ports should be declared as a wire in the test bench. Also, do not connect module port to cross module references, such as dut.foo. \n
Example response:
{
	"test bench": "
		module tb_llm;

			// Clock logic

			initial
			begin
				// Generted test cases
			$finish;
			end
		endmodule
	",
	"comments": " // Any additonal comments here "
}
'''


def error_prompt(error_code: int, error_message: str) -> str:

	# Handle error responses from QuestaSim
	if error_code == 1:
		return f'''The generated test bench failed to compile. Use the following error message to fix the errors. Use the same JSON format for the new testbench. Error Message:\n{error_message}\nProvide the generated testbench in a JSON format as shown below. You should put the generated test bench into the \"test bench\" tag and any additonal comments into the \"comments\" tag. Keep the test bench less than 500 lines. Ensure that there is only one testbench within the JSON formatted output.\n
Here are some additional guidelines for the test bench: \n
Please declare signals before using them. When instantiating the DUT, the signals connected to the input ports should be declared as a reg in the test bench. When instantiating the DUT, the signals connected to the output ports should be declared as a wire in the test bench. Also, do not connect module port to cross module references, such as dut.foo. \n''' + '''Example response:
{
	"test bench": "
		module tb_llm;

			// Clock logic

			initial
			begin
				// Generted test cases
			$finish;
			end
		endmodule
	",
	"comments": " // Any additonal comments here "
}
'''
	elif error_code == 2:
		return f'''The generated test bench failed to simulate. Use the following error message to fix the errors Use the same JSON format for the new testbench. Error Message:\n{error_message}\nProvide the generated testbench in a JSON format as shown below. You should put the generated test bench into the \"test bench\" tag and any additonal comments into the \"comments\" tag. Keep the test bench less than 500 lines. Ensure that there is only one testbench within the JSON formatted output.\n
Here are some additional guidelines for the test bench: \n
Please declare signals before using them. When instantiating the DUT, the signals connected to the input ports should be declared as a reg in the test bench. When instantiating the DUT, the signals connected to the output ports should be declared as a wire in the test bench. Also, do not connect module port to cross module references, such as dut.foo. \n''' + '''Example response:
{
	"test bench": "
		module tb_llm;

			// Clock logic

			initial
			begin
				// Generted test cases
			$finish;
			end
		endmodule
	",
	"comments": " // Any additonal comments here "
}
'''
	elif error_code == 3:
		return f'''The generated test bench took to long to simulate and timed out. Try to shorten the testbench. Use the same JSON format for the new testbench. Provide the generated testbench in a JSON format as shown below. You should put the generated test bench into the \"test bench\" tag and any additonal comments into the \"comments\" tag. Keep the test bench less than 500 lines. Ensure that there is only one testbench within the JSON formatted output.\n
Here are some additional guidelines for the test bench: \n
Please declare signals before using them. When instantiating the DUT, the signals connected to the input ports should be declared as a reg in the test bench. When instantiating the DUT, the signals connected to the output ports should be declared as a wire in the test bench. Also, do not connect module port to cross module references, such as dut.foo. \n''' + '''Example response:
{
	"test bench": "
		module tb_llm;

			// Clock logic

			initial
			begin
				// Generted test cases
			$finish;
			end
		endmodule
	",
	"comments": " // Any additonal comments here "
}
'''
	elif error_code == 4:
		return f'''You failed to generate a test bench in the JSON format I have specified. You MUST use this JSON format so I can parse your response correctly. You may have also either generated a terminating token too early, ran past the token limit, or took too long to generate. Try generating a shorter test bench with higher quality tests. Use the same JSON format for the new testbench. Provide the generated testbench in a JSON format as shown below. You should put the generated test bench into the \"test bench\" tag and any additonal comments into the \"comments\" tag. Keep the test bench less than 500 lines. Ensure that there is only one testbench within the JSON formatted output.\n
Here are some additional guidelines for the test bench: \n
Please declare signals before using them. When instantiating the DUT, the signals connected to the input ports should be declared as a reg in the test bench. When instantiating the DUT, the signals connected to the output ports should be declared as a wire in the test bench. Also, do not connect module port to cross module references, such as dut.foo. \n''' + '''Example response:
{
	"test bench": "
		module tb_llm;

			// Clock logic

			initial
			begin
				// Generted test cases
			$finish;
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
def m3_prompt(coverage: CoverageResponse, top_design_module: str) -> str:

	if coverage.error_code != 0:
		return error_prompt(coverage.error_code, coverage.error_message)
	
	if coverage.total_coverage <= 0:
		return '''You may have generated an empty test bench because there was no code coverage of the design.
		Please remember to format your response properly. We want you to put the test bench you think will achieve the most covergage
		inside of the JSON. Please see the format below again for reference:
		Example response:
		{
			"test bench": "
				module tb_llm;

					// Clock logic

					initial
					begin
						// Generted test cases
					$finish;
					end
				endmodule
			",
			"comments": " // Any additonal comments here "
		}
		'''

	formatted_coverage_report = f"Total Design Coverage: {coverage.total_coverage}\n"
	missed_lines = {}

	for inst in coverage.coverage_list:
		design_unit = inst.du
		for stmt in inst.coverage_details:
			if stmt.get('hits') == '0':
				line = int(str(stmt.get('ln')))
				if design_unit not in missed_lines:
					missed_lines[design_unit] = {"path": inst.path, "lines": []}
				missed_lines[design_unit]["lines"].append(line) # type: ignore

		formatted_coverage_report += f"File: {os.path.split(inst.path)[1]}\tDesign Unit: {design_unit}\tActive: {inst.coverage['active']}\tHits: {inst.coverage['hits']}\tPercent: {inst.coverage['percent']}\n"

	if not missed_lines:
		return "No missed lines left to fix"

	# Prioritize missed lines
	prioritized_misses = prioritize_missed_lines(missed_lines)

	if not prioritized_misses:
		return "No valid missed lines found."

	rand_du, missed_line, rand_du_filepath = prioritized_misses[0]
	rand_du_filename = os.path.split(rand_du_filepath)[1]

	try:
		with open(rand_du_filepath, 'r') as f:
			lines = f.readlines()
	except FileNotFoundError:
		return f"Error: Could not open file {rand_du_filepath}."

	lines[missed_line - 1] = lines[missed_line - 1].replace('\n', "\t// This is a line that was not covered\n")

	start_line = None
	end_line = None

	# Loop through the lines to find the module definition
	for i, line in enumerate(lines):
		if re.match(rf"\s*module\s+{rand_du}\b", line):
			start_line = i
		if re.match(r"\s*endmodule\b", line) and start_line is not None:
			end_line = i
			break  # Stop after finding the first matching module

	module = ""
	if start_line is not None and end_line is not None:
		module = ''.join(lines[start_line:end_line])

	return '''The test bench that you generated did not meet coverage goals. Use the following coverage data and context to generate a test bench that achieves better coverage:
''' + formatted_coverage_report + f'''
A missed line was detected in the module {rand_du}, located in {rand_du_filename}, specifically at line {missed_line}.
Important:
1. The test bench should ONLY be generated for the top-level module {top_design_module}, even if the missed line exists in a submodule.
2. Ensure the test bench stimualtes {top_design_module} in a way that excercises the missing coverage in {rand_du}.
3. Think about what signals it would take to drive in {top_design_module} to hit the coverage hole in {rand_du}.

Here is {rand_du} with a coverage hole marked for you:
{module}

There are three options for improving line coverage, choose one of these option:
1. Add another testcase to a previously generated testbench
2. Modify a testcase from a previously generated testbench
3. Generate a completely new testbench without previous generations as context

It is important to ensure that the generated test case is novel and does not duplicate existing patterns. Modify input sequences and edge cases where possible.

Generate a Verilog testbench named tb_llm for the the top-level module {top_design_module}.
The test bench should meet the statement coverage goal of 100%.
Generate only the Verilog testbench and no additional words.
Make sure you are ONLY using Verilog syntax and features, and not SystemVerilog such as for loops and asserts.\n
Provide the generated testbench in a JSON format as shown below. You should put the generated test bench into the "test bench" tag and any additonal comments into the "comments" tag. Keep the test bench less than 500 lines. Ensure that there is only one testbench within the JSON formatted output.\n
Here are some additional guidelines for the test bench: \n
Please declare signals before using them. When instantiating the DUT, the signals connected to the input ports should be declared as a reg in the test bench. When instantiating the DUT, the signals connected to the output ports should be declared as a wire in the test bench. Also, do not connect module port to cross module references, such as dut.foo. \n
''' + '''Example response:
{
	"test bench": "
		module tb_llm;

			// Clock logic

			initial
			begin
				// Generted test cases
			$finish;
			end
		endmodule
	",
	"comments": " // Any additonal comments here "
}
'''

def prioritize_missed_lines(missed_lines):
	"""
	Prioritize missed lines based on their control flow importance
	"""

	prioritized = []

	for du, details in missed_lines.items():
		try:
			with open(details["path"], 'r') as f:
				lines = f.readlines()

			for line_num in details["lines"]:
				code_line = lines[line_num - 1].strip()

				if re.search(r'if\s*\(|case\s*\(|while\s*\(|for\s*\(', code_line):
					prioritized.insert(0, (du, line_num, details["path"]))  # Insert at front
				else:
					prioritized.append((du, line_num, details["path"]))  # Append at back
        
		except (FileNotFoundError, IndexError):
			continue  # Skip if file is missing or line number is out of range
	
	return prioritized

def design_prompt(all_design_files: list[str]) -> str:

	base: str = "Here is the full design to give you more context about the logic of each module:\n\n"

	for file_path in all_design_files:
		with open(file_path, 'r') as f:
			base += f"{file_path}:\n{f.read()}\n\n"

	return base
