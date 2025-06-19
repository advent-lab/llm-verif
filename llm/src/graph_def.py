from langgraph.graph import StateGraph, END
from agents import test_plan_agent, test_bench_agent, coverage_agent, reasoning_agent
from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from simulator import Simulator

from IPython.display import Image, display

class State(TypedDict):
  design_spec: str
  module_header: str
  testbench_path: str
  test_plan: str
  test_bench: str
  coverage: dict
  improvement_directive: str
  data_point: str
  log_name: str
  simulator: Simulator
  error: str
  error_code: int
  total_coverage: float
  
  messages: Annotated[list[str], add_messages]

builder = StateGraph(State)

builder.add_node("TestPlan", test_plan_agent)
builder.add_node("TestBench", test_bench_agent)
builder.add_node("Coverage", coverage_agent)
builder.add_node("Reasoning", reasoning_agent)

builder.set_entry_point("TestPlan")
builder.add_edge("TestPlan", "TestBench")
builder.add_edge("TestBench", "Coverage")
builder.add_edge("Coverage", "Reasoning")

def condition_router(state: dict) -> str:
  return END if state.get("improvment_directive") == "STOP" else "TestBench"

builder.add_conditional_edges("Reasoning", condition_router)

graph = builder.compile()

print(graph.get_graph().draw_ascii())