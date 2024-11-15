from src.questasim import CoverageResponse
import os
import pathlib
from random import randint

# This function returns the initial prompt used for generating a test bench
def m1_prompt(design_specification: str, module_header: str) -> str:
    return f'''Generate a Verilog testbench named tb_llm for the following design specification.
The test bench should meet the statement coverage goal of 100%.
Generate only the Verilog testbench and no additional words.
Make sure you are ONLY using Verilog syntax and features, and not SystemVerilog such as for loops.\n
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
def m2_prompts(design_specification: str, module_header: str) -> (str, str):
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

def m3_prompt(design_file: str, coverage: CoverageResponse) -> str:

	# Handle error responses from QuestaSim
	if coverage.error_code == 1:
		return f"The generated test bench failed to compile. Use the following error message to fix the errors. Use the same JSON format for the new testbench. Error Message:\n{coverage.error_message}\nProvide the generated testbench in a JSON format as shown below. You should put the generated test bench into the \"test bench\" tag and any additonal comments into the \"comments\" tag. Keep the test bench less than 500 lines.\n" + '''Example output:
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
	elif coverage.error_code == 2:
		return f"The generated test bench failed to simulate. Use the following error message to fix the errors Use the same JSON format for the new testbench. Error Message:\n{coverage.error_message}\nProvide the generated testbench in a JSON format as shown below. You should put the generated test bench into the \"test bench\" tag and any additonal comments into the \"comments\" tag. Keep the test bench less than 500 lines.\n" + '''Example output:
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
	elif coverage.error_code == 3:
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
	elif coverage.error_code == 4:
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

	design_filename = os.path.split(design_file)[1]

	formatted_coverage_report = ""
	missed_lines = []
	for inst in coverage.coverage_list:
		if os.path.split(inst['path'])[1] == design_filename:
			for stmt in inst['coverage_detail']:
				if stmt['hits'] == '0':
					missed_lines.append(int(stmt['ln']))
		
		formatted_coverage_report += f"File: {os.path.split(inst['path'])[1]}\tActive: {inst['coverage']['active']}\tHits: {inst['coverage']['hits']}\tPercent: {inst['coverage']['percent']}\n"

	if not missed_lines:
		return None

	with open(design_file, 'r') as f:
		lines = f.readlines()

	randline = randint(0, len(missed_lines) - 1)

	lines[missed_lines[randline] - 1] = lines[missed_lines[randline] - 1].replace('\n', " // This is the line that was not covered\n")

	missed_line = lines[missed_lines[randline] - 1]
	design_chunk = ''.join(lines[missed_lines[randline] - 10:missed_lines[randline] + 11])

	return '''The test bench that you generated did not meet coverage goals. Use this coverage data and context to generate a test bench that achieves better coverage.
Coverage report:
''' + formatted_coverage_report + f'''
I will give you some extra context to help. Try to target this coverage hole at line {missed_lines[randline]} in the file {design_filename}: {missed_line.strip()}
{design_chunk}

Generate a Verilog testbench named tb_llm for the following design specification.
The test bench should meet the statement coverage goal of 100%.
Generate only the Verilog testbench and no additional words.
Make sure you are ONLY using Verilog syntax and features, and not SystemVerilog such as for loops.\n
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

def design_prompt(design_file: str) -> str:

	with open(design_file, 'r') as f:
		lines = f.readlines()

	design_chunk = ''.join(lines)

	return f'''The test bench that you generated did not meet coverage goals. 
I will give you some extra context to help. Here is the design for the main design module:
{design_chunk}

Generate a Verilog testbench named tb_llm for the following design specification.
The test bench should meet the statement coverage goal of 100%.
Generate only the Verilog testbench and no additional words.
Make sure you are ONLY using Verilog syntax and features, and not SystemVerilog such as for loops.\n
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