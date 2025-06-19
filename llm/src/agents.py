from langchain.chat_models import init_chat_model
from langchain.schema import SystemMessage, HumanMessage

from questasim import QuestaSim
from util import convert_json_response_to_dict

llm  = init_chat_model(model="gpt-4", temperature=0.3)

def test_plan_agent(state: dict) -> dict:
    spec = state["design_spec"]
    messages = [
        SystemMessage(content='''You are an expert Verilog verification assistant. You have expertise in writing high quality, high code coverage test bench for a wide variety of digital hardware designs.

Directions:

When generating a verification plan or test plan, You should generate a verification plan with test scenarios that will achieve full statement coverage of the design.
Your verification plan should cover as many valid and invalid sets of stimulus as possible to ensure you can reach the maximum coverage possible.
'''
        ),
        HumanMessage(content=f"Generate a verification plan for the following design:\n\n{spec}")
    ]

    response = llm.invoke(messages)

    state["test_plan"] = response.content
    
    return state

def test_bench_agent(state: dict) -> dict:
    plan = state["test_plan"]

    # Use fallback if improvement_directive is missing or empty
    directive = state.get("improvement_directive", "").strip()
    if not directive:
        directive = "Generate a completely new testbench."

    print(state)
    messages = [
        SystemMessage(content='''You are an expert Verilog verification assistant. You have expertise in writing high quality, high code coverage test bench for a wide variety of digital hardware designs.

Directions:

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
        ),
        HumanMessage(content=f"{directive}\nGenerate a testbench for the following specification and plan:\n\nModule Header:\n{state['module_header']}\n\nSpecification:\n{state['design_spec']}\n\nTest plan:\n{plan}")
    ]

    response = llm.invoke(messages)

    parsed_response, status_code = convert_json_response_to_dict(str(response.content))
    if status_code != 0:
        raise RuntimeError(f"Failed to parse test bench response: {response.content}")

    state["test_bench"] = parsed_response["test bench"]

    return state

def coverage_agent(state: dict) -> dict:
    simulator: QuestaSim = state["simulator"]

    test_bench = state["test_bench"]
    testbench_path = state["testbench_path"]
    log_name = state["log_name"]

    with open(testbench_path, "w+") as testbench_file:
        testbench_file.write(test_bench)

    coverage_response = simulator.run_sim(testbench_path, state["data_point"], log_name)

    
    state["error_code"] = coverage_response.error_code
    state["coverage"] = coverage_response.coverage_list
    state["total_coverage"] = coverage_response.total_coverage
    state["error"] = coverage_response.error_message
    
    return state
    

def reasoning_agent(state: dict) -> dict:
    if state["total_coverage"] == 100:
        state["improvment_directive"] = "STOP"
        return state

    messages = [
        SystemMessage(content='''You are an expert at reasoning about the coverage of Verilog test benches.
                      
It is very important that you carefully think about how to fix any errors in the test bench, if they exist, and how to improve the coverage of the test bench.
'''
        ),
        HumanMessage(content=f"Given the following test bench and coverage results, what should be done to improve the coverage?\n\nTest Bench:\n{state['test_bench']}\n\nSimulator Results:{state['error']}\n\nCoverage Results:\n{state['coverage']}\n\nTotal Coverage: {state['total_coverage']}%\n\nPlease provide a directive on how to improve the coverage.")
    ]

    state["improvement_directive"] = llm.invoke(messages).content

    print(state["improvement_directive"])

    return state
