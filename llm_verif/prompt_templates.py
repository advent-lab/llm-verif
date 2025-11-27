from llm_verif.questasim import CoverageResponse

def system_prompt(design_specification: str, module_header: str,design_content: list[str] | None = None):

	design_message = ""
	if design_content:
		design_message = design_prompt(design_content)

	return f"""You are an expert Verilog verification assistant. You have expertise in writing high quality, high code coverage testbench for a wide variety of digital hardware designs.       

The testbench refers to the top-level module in which the DUT is instantiated. Additionally, there is code to generate clocks and sometimes resets in the testbench. A testcase refers to stimulus applied to the signals connected to the DUT's ports. In plain Verilog based testbenches, a testcase is written inside the testbench file inside initial blocks. A testcase may be organized using tasks and functions that can be called from an initial block. For example:

initial begin
  reset = 0;
  #10;
   reset = 1;
  #10;
  apb_write(); //task call
  wait(); //task call
  apb_read();  //task call
  $finish();  
end

In System Verilog based testbenches, a testcase is written in tasks and functions inside classes. These tasks and functions drive signals on the DUT through a virtual interface. The top-level class is usually created inside an initial block in the testbench and the top-level task is called. For example:

initial begin
  stimulus stim = new();  //creating the stimulus class
  stim.vif = interface_inst; //the instance of an interface containing the DUT's port signals
  stim.run();  //the main task inside the object
end

A verification plan or a test plan is a document that includes the description of the verification strategy, the testbench architecture, and the various scenarios to test each feature of the DUT or design. At times you will need to generate a verification plan or a test plan. When generating a verification plan or test plan, you should generate a plan with test scenarios that will achieve full statement coverage of the design. Your plan should cover as many sets of stimulus as possible to ensure you can reach the maximum coverage possible. Your plan should mention the values and timings of various signals/variables that should be randomized. You plan should mention constraints on values and timings as well.

At other times, you will generate a testbench. The goal of the testbench is to include testcases that can achieve a 100% line coverage of the DUT code. When generating a testbench, there are two options for improving line coverage, choose one of these options:
1. Start from a testcase from a previously generated testbench. Modify the stimulus in it, or remove stimulus from it, or add extra stimulus  to it.
2. Start a fresh testcase without using the previous generations as context. This will have new stimulus required to hit the coverage point being targeted.
                         
We will run multiple iterations. In each iteration, you will generate a testbench - using one of the options mentioned above. Your goal should be to cover as much as statement coverage goal as possible. Across multiple iterations, we aim to have a coverage of 100%.

The module name of the testbench should be tb_llm.
You can use either Verilog or SystemVerilog syntax and features. Do not generate any UVM code.
If you use SystemVerilog classes, declare them before the top-level testbench module.

Below are a specification for the design you are trying to verify and a module header for the top-level module of the design. Use this information to generate the testbench.

Module Header:
{module_header}

Design Specification:
{design_specification}
""" + design_message

def zero_shot_prompt() -> str:
	return '''Generate a testbench for the following design specification.
Generate a Verilog testbench named tb_llm for the top-level module. The test bench should meet the statement coverage goal of 100%.

The module name of the testbench should be tb_llm.
You can use either Verilog or SystemVerilog syntax and features. Do not generate any UVM code.

Additional guidelines:
- Please declare signals before using them
- When instantiating the DUT, signals connected to input ports should be declared as reg
- Signals connected to output ports should be declared as wire
- Do not connect module ports to cross module references (such as dut.foo)
'''

# This function returns the initial prompt used for generating a test bench
def first_testbench_prompt(design_specification: str | None = None, module_header: str | None = None) -> str:
    return '''Generate a testbench for the given design specification and module header.
Generate a Verilog testbench named tb_llm for the top-level module. The test bench should meet the statement coverage goal of 100%.

The module name of the testbench should be tb_llm.
You can use either Verilog or SystemVerilog syntax and features. Do not generate any UVM code.

Additional guidelines for the testbench:
- Please declare signals before using them
- When instantiating the DUT, signals connected to input ports should be declared as reg
- Signals connected to output ports should be declared as wire
- Do not connect module ports to cross module references (such as dut.foo)

When you generate the testcase, randomize the appropriate signals to get as much coverage as possible. You can randomize signals using $urandom, $urandom_range, or randomize(). Please do not use $random as it lacks random stability. If you use the randomize(), ensure that you enclose the call in an assert(), so that if the randomization fails, an error is produced.

Here's an example of a simple piece of code doing randomization on signals/variables names sigA, sigB, sigC, sigD, and sigE, and also on delays.

initial begin
  reset = 0;
  #10;
  reset = 1;
  sigA = $urandom();
  sigB = $urandom_range(10,20);  //randomize within a range
  assert(randomize(sigC));  //use the std::randomize() method
  success = randomize(sigD, sigE) with {{sigD < sigE; sigD + sigE < 2;}};  //std::randomize() with constraints
  assert(success);
  
  delay = $urandom_range(10,100); 
  repeat (delay) @(posedge clk);  //waiting random number of cycles
  sigA = $urandom();
  sigB = $urandom_range(10,20);  //randomize within a range
 end
  
If you are using System Verilog classes, make sure you declare rand variables and then call .randomize() on the class objects. You can have constraints inside the class declaration or inline constraints when calling .randomize(). Here's some example code:

class SimpleSum;
  rand bit [7:0] x, y, z;
  constraint c {{z == x + y;}}
endclass

SimpleSum p = new;
int success = p.randomize();

SimpleSum p = new;
int success = p.randomize() with {{x < y}};

Remember that when you use System Verilog classes for the testcases, you should create an interface, instantiate the interface, connect the right signals to it, and pass the handle to the interface to the class object.
'''

def verification_plan_prompt() -> str:
	prompt = f"""You are a hardware verification expert. Your task is to generate a *comprehensive* and *structured* verification plan for a SystemVerilog testbench that targets the design described below.

Objective
Generate a detailed verification plan that will achieve full statement coverage of the design. Focus on thorough test scenario planning, including normal, boundary, corner, and illegal input cases where applicable. This is **stage 1** of a two-stage testbench generation process.

Guidelines for a Good Verification Plan
A strong verification plan should:
- Identify **test objectives** derived from functional and structural elements of the design in the specification.
- Include **test scenarios** organized by functionality, interface, or behavior.
- Target all **control paths**, **edge conditions**, and **expected behaviors** (e.g., valid/invalid inputs, reset behavior, concurrent conditions).
- Explicitly mention which statements or coverage goals are exercised by each scenario.
- Include **justification** for how each test contributes to coverage.
- Optionally recommend **checkers** or **assertions** if useful for complex conditions.

Output Format
Return the verification plan in a structured format like:

Test Objective: [Goal]

Description: [What feature/behavior is being tested]

Stimulus: [Inputs or sequences required to exercise it]

Expected Outcome: [What the DUT should do]

Coverage Goal: [Statements/branches/scenarios covered]

Notes: [Optional rationale or dependencies]

List multiple such entries, grouped where appropriate by:

Interface behavior

Control flow paths

Data path/logic scenarios

Special conditions (reset, edge cases, assertions)

Begin writing the verification plan now:
"""
	return prompt

# This function returns two prompts
# The first prompt should be used to generate the verification plan
# The second prompt should be used to generate the test bench after the verification plan is generated
# The second prompt assumes that conversation histroy is being provided to the LLM in addition to the second prompt
def verif_and_testbench_prompt(crt: bool = True) -> tuple[str, str]:
    p1 = verification_plan_prompt()
    p2 = '''Now we are in the second stage of the verification process.''' + first_testbench_prompt() if crt else zero_shot_prompt()
    return (p1, p2)

def error_prompt(error_code: int, error_message: str) -> str:

	# Handle error responses from simulators
	if error_code == 1:
		return f'''The generated testbench failed to compile. Use the following error message to fix the errors.

Error Message:
{error_message}

Additional guidelines:
- Please declare signals before using them
- When instantiating the DUT, signals connected to input ports should be declared as reg
- Signals connected to output ports should be declared as wire
- Do not connect module ports to cross module references (such as dut.foo)
'''
	
	elif error_code == 2:
		return f'''The generated testbench failed to simulate. Use the following error message to fix the errors.

Error Message:
{error_message}

Additional guidelines:
- Please declare signals before using them
- When instantiating the DUT, signals connected to input ports should be declared as reg
- Signals connected to output ports should be declared as wire
- Do not connect module ports to cross module references (such as dut.foo)
'''
	
	elif error_code == 3:
		return f'''The generated testbench took too long to simulate and timed out. Try to shorten the testbench.

Additional guidelines:
- Please declare signals before using them
- When instantiating the DUT, signals connected to input ports should be declared as reg
- Signals connected to output ports should be declared as wire
- Do not connect module ports to cross module references (such as dut.foo)
'''
	
	elif error_code == 4:
		return '''The response generation failed. You may have generated a terminating token too early, ran past the token limit, or took too long to generate. Try generating a shorter testbench with higher quality tests.

Additional guidelines:
- Please declare signals before using them
- When instantiating the DUT, signals connected to input ports should be declared as reg
- Signals connected to output ports should be declared as wire
- Do not connect module ports to cross module references (such as dut.foo)
'''
	
	elif error_code == 5:
		return "You did not add a $finish command to your testbench so I cannot simulate it. Please add the $finish command in the correct place in the testbench."

	return ""

# --- main prompt builder -----------------------------------------------------

def iter_prompt(
    coverage: "CoverageResponse",
    top_design_module: str,
    simulator,  # Simulator instance (QuestaSim or Verilator)
    work_dir: str,
) -> str:
    """
    Generate an iteration prompt using simulator-specific coverage feedback.

    This function delegates coverage formatting and feedback extraction to the
    simulator implementation, maintaining simulator independence.
    """
    # Handle error cases
    if coverage.error_code != 0:
        return error_prompt(coverage.error_code, coverage.error_message)

    if coverage.total_coverage <= 0:
        return f'''You may have generated a testbench with an uncaught error or that is empty because there was no code coverage of the design.

Error Message: {coverage.error_message}

Please generate a testbench that will achieve maximum coverage for the design.
'''

    # Use simulator-specific methods for coverage formatting
    coverage_summary = simulator.format_coverage_summary(coverage)
    coverage_feedback = simulator.extract_coverage_feedback(coverage, top_design_module, work_dir)

    # Build the prompt using simulator-agnostic structure
    return (
        "The testbench that you generated did not meet coverage goals. "
        "Use the following coverage data and context to generate a testbench that achieves better coverage:\n\n"
        + coverage_summary + "\n\n"
        + coverage_feedback + "\n\n"
        + f"""There are two options for improving line coverage; choose one:
1) Modify an existing testcase from a previous testbench (adjust/add/remove stimulus).
2) Start a fresh testcase with novel stimulus to target the uncovered logic.

Generate a Verilog testbench named tb_llm for top module {top_design_module}.
The testbench should target 100% statement coverage.
"""
    )

def design_prompt(all_design_files: list[str]) -> str:

	base: str = "Here is the full design to give you more context about the logic of each module:\n\n"

	for file_path in all_design_files:
		with open(file_path, 'r') as f:
			base += f"{file_path}:\n{f.read()}\n\n"

	return base
