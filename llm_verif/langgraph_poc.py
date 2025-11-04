"""
LangGraph Proof of Concept - Phase 1 Implementation

This demonstrates the basic structure of the LangGraph-based verification framework
with core agents (Planner, Generator, Critic, Simulator, Grader, Refiner).
"""

import asyncio
from typing import TypedDict, List, Dict, Any, Annotated, Literal
from dataclasses import dataclass
import operator
import json

# LangGraph imports
from langgraph.graph import StateGraph, END

# Existing framework imports (to be integrated)
from llm_verif.prompt_templates import (
    system_prompt,
    verification_plan_prompt,
    first_testbench_prompt,
    iter_prompt,
    error_prompt
)


# ============================================================================
# STATE DEFINITION
# ============================================================================

class VerificationState(TypedDict):
    """
    Central state object that flows through the LangGraph.
    Uses Annotated with operator.add for append-only fields.
    """
    # Design context
    design_spec: str
    module_header: str
    design_files: List[str]

    # Conversation history (append-only)
    messages: Annotated[List[Dict[str, str]], operator.add]

    # Planning
    verification_plan: Dict[str, Any]
    plan_available: bool

    # Generation
    current_testbench: str
    current_testbench_comments: str
    generated_testbenches: Annotated[List[Dict], operator.add]
    generation_count: int
    batch_candidates: List[str]

    # Critique (NEW)
    critique_results: Dict[str, Any]

    # Simulation
    simulation_results: Dict[str, Any]

    # Grading (NEW)
    grading_results: Dict[str, Any]

    # Iteration tracking
    iteration: int
    valid_iterations: int
    max_coverage: float
    coverage_history: Annotated[List[float], operator.add]

    # Configuration
    max_iterations: int
    max_valid_iter: int
    batch_size: int
    temperature: float

    # Control flow
    next_action: str  # "continue", "complete", "stuck"
    skip_planning: bool


# ============================================================================
# AGENT IMPLEMENTATIONS
# ============================================================================

async def planner_agent(state: VerificationState, llm_backend) -> Dict[str, Any]:
    """
    Agent 1: Planner
    Generates high-level verification strategy and test plan.
    """
    print(f"[Planner Agent] Starting verification planning...")

    # Skip if planning disabled or plan already exists
    if state.get("skip_planning") or state.get("plan_available"):
        print(f"[Planner Agent] Skipping (plan_available={state.get('plan_available')}, skip={state.get('skip_planning')})")
        return {"plan_available": True}

    # Build planning prompt
    prompt = verification_plan_prompt()

    # Call LLM
    try:
        response, tokens, elapsed = await llm_backend.generate_response_async(
            conversation_history=None,  # Planning uses fresh context
            system_message=system_prompt(
                state["design_spec"],
                state["module_header"],
                state.get("design_files", [])
            ),
            user_message=prompt,
            temperature=0.7,
            num_return_sequences=1
        )

        # Parse plan (simple JSON extraction)
        plan = parse_json_from_response(response[0])

        print(f"[Planner Agent] Plan generated successfully ({tokens} tokens, {elapsed:.2f}s)")

        return {
            "verification_plan": plan,
            "plan_available": True,
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response[0]}
            ]
        }

    except Exception as e:
        print(f"[Planner Agent] Error: {e}")
        # Fallback to empty plan
        return {
            "verification_plan": {"objectives": [], "scenarios": []},
            "plan_available": True
        }


async def generator_agent(state: VerificationState, llm_backend) -> Dict[str, Any]:
    """
    Agent 2: Generator
    Generates SystemVerilog testbenches from specifications/feedback.
    """
    iteration = state.get("iteration", 0)
    print(f"[Generator Agent] Generating testbench (iteration {iteration})...")

    # Determine prompt based on iteration
    if iteration == 0:
        # Initial generation
        prompt = first_testbench_prompt(
            state["design_spec"],
            state["module_header"],
            state.get("verification_plan", {})
        )
    else:
        # Refinement generation
        prompt = build_refinement_prompt(state)

    # Build conversation context
    messages = state.get("messages", [])

    try:
        # Generate with batch support
        batch_size = state.get("batch_size", 1)
        temperature = state.get("temperature", 0.7)

        responses, tokens, elapsed = await llm_backend.generate_response_async(
            conversation_history=None,
            system_message=system_prompt(
                state["design_spec"],
                state["module_header"],
                state.get("design_files", [])
            ),
            user_message=prompt,
            temperature=temperature,
            num_return_sequences=batch_size
        )

        # Parse testbenches
        testbenches = []
        for resp in responses:
            parsed = parse_testbench_response(resp)
            testbenches.append(parsed)

        # Select first as current (batch evaluation happens later)
        current_tb = testbenches[0]

        print(f"[Generator Agent] Generated {len(testbenches)} testbench(es) ({tokens} tokens, {elapsed:.2f}s)")

        return {
            "current_testbench": current_tb["test_bench"],
            "current_testbench_comments": current_tb.get("comments", ""),
            "batch_candidates": [tb["test_bench"] for tb in testbenches],
            "generation_count": state.get("generation_count", 0) + 1,
            "generated_testbenches": [
                {
                    "code": tb["test_bench"],
                    "iteration": iteration,
                    "source": "initial" if iteration == 0 else "refined"
                }
                for tb in testbenches
            ],
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": responses[0]}
            ]
        }

    except Exception as e:
        print(f"[Generator Agent] Error: {e}")
        # Return error state
        return {
            "current_testbench": "",
            "next_action": "error"
        }


async def critic_agent(state: VerificationState, llm_backend) -> Dict[str, Any]:
    """
    Agent 3: Critic (NEW)
    Pre-simulation quality assessment and code review.
    """
    print(f"[Critic Agent] Reviewing testbench quality...")

    code = state.get("current_testbench", "")
    if not code:
        print(f"[Critic Agent] No testbench to review, skipping")
        return {
            "critique_results": {"recommendation": "reject", "score": 0}
        }

    # Build critique prompt
    prompt = build_critique_prompt(
        state["design_spec"],
        code,
        state.get("verification_plan", {})
    )

    try:
        response, tokens, elapsed = await llm_backend.generate_response_async(
            conversation_history=None,
            system_message="You are an expert SystemVerilog verification engineer performing code review.",
            user_message=prompt,
            temperature=0.3,  # Lower temperature for analytical tasks
            num_return_sequences=1
        )

        # Parse critique
        critique = parse_json_from_response(response[0])

        score = critique.get("critique_score", 0)
        recommendation = critique.get("recommendation", "revise")
        issues_count = len(critique.get("issues", []))

        print(f"[Critic Agent] Review complete: {recommendation.upper()} (score: {score}/100, {issues_count} issues)")

        return {
            "critique_results": critique,
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response[0]}
            ]
        }

    except Exception as e:
        print(f"[Critic Agent] Error: {e}")
        # Fallback to approve (don't block on critic failure)
        return {
            "critique_results": {
                "recommendation": "approve",
                "critique_score": 50,
                "issues": [],
                "reasoning": "Critic failed, proceeding to simulation"
            }
        }


def simulator_node(state: VerificationState, simulator) -> Dict[str, Any]:
    """
    Node: Simulator
    Executes testbench and collects coverage (uses existing simulator).
    """
    print(f"[Simulator Node] Running simulation...")

    code = state.get("current_testbench", "")
    iteration = state.get("iteration", 0)

    try:
        # Use existing simulator interface
        cov_response = simulator.run_simulation_flow(
            testbench_code=code,
            iteration=iteration,
            file_stem=f"tb_iter_{iteration}"
        )

        success = cov_response.success
        coverage = cov_response.total_coverage

        print(f"[Simulator Node] Simulation {'PASSED' if success else 'FAILED'}: {coverage:.2f}% coverage")

        # Update max coverage
        max_cov = max(state.get("max_coverage", 0), coverage)

        return {
            "simulation_results": {
                "success": success,
                "error_code": cov_response.error_code,
                "coverage": coverage,
                "coverage_list": cov_response.coverage_list,
                "error_message": cov_response.error_message,
                "coverage_summary": simulator.format_coverage_summary(cov_response),
                "coverage_feedback": simulator.extract_coverage_feedback(cov_response)
            },
            "max_coverage": max_cov,
            "coverage_history": [coverage],
            "valid_iterations": state.get("valid_iterations", 0) + (1 if success else 0)
        }

    except Exception as e:
        print(f"[Simulator Node] Error: {e}")
        return {
            "simulation_results": {
                "success": False,
                "error_code": 99,
                "coverage": 0.0,
                "error_message": str(e)
            }
        }


async def grader_agent(state: VerificationState, llm_backend) -> Dict[str, Any]:
    """
    Agent 4: Grader (NEW)
    Post-simulation quality assessment and learning feedback.
    """
    print(f"[Grader Agent] Grading testbench results...")

    sim_results = state.get("simulation_results", {})
    if not sim_results.get("success"):
        print(f"[Grader Agent] Simulation failed, skipping grading")
        return {
            "grading_results": {
                "overall_grade": "F",
                "continue": True,
                "reasoning": "Simulation failed, needs fixing"
            }
        }

    # Build grading prompt
    prompt = build_grading_prompt(
        state["design_spec"],
        state["current_testbench"],
        sim_results,
        state.get("max_coverage", 0),
        state.get("coverage_history", [])
    )

    try:
        response, tokens, elapsed = await llm_backend.generate_response_async(
            conversation_history=None,
            system_message="You are a verification quality grading expert analyzing testbench effectiveness.",
            user_message=prompt,
            temperature=0.4,
            num_return_sequences=1
        )

        # Parse grading
        grading = parse_json_from_response(response[0])

        grade = grading.get("overall_grade", "C")
        quality = grading.get("quality_score", 50)
        continue_flag = grading.get("continue_iteration", True)

        print(f"[Grader Agent] Grade: {grade} (quality: {quality}/100, continue: {continue_flag})")

        return {
            "grading_results": grading,
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response[0]}
            ]
        }

    except Exception as e:
        print(f"[Grader Agent] Error: {e}")
        # Fallback to continue
        return {
            "grading_results": {
                "overall_grade": "C",
                "continue_iteration": True,
                "reasoning": "Grader failed, continuing iteration"
            }
        }


async def refiner_agent(state: VerificationState, llm_backend) -> Dict[str, Any]:
    """
    Agent 5: Refiner
    Targeted improvements based on multi-agent feedback.
    """
    iteration = state.get("iteration", 0)
    print(f"[Refiner Agent] Refining testbench (iteration {iteration})...")

    # Build refinement prompt with all feedback
    prompt = build_refinement_prompt_with_feedback(state)

    try:
        response, tokens, elapsed = await llm_backend.generate_response_async(
            conversation_history=None,
            system_message=system_prompt(
                state["design_spec"],
                state["module_header"],
                state.get("design_files", [])
            ),
            user_message=prompt,
            temperature=get_adaptive_temperature(state),
            num_return_sequences=1
        )

        # Parse refined testbench
        testbench = parse_testbench_response(response[0])

        print(f"[Refiner Agent] Refinement complete ({tokens} tokens, {elapsed:.2f}s)")

        return {
            "current_testbench": testbench["test_bench"],
            "current_testbench_comments": testbench.get("comments", ""),
            "iteration": iteration + 1,
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response[0]}
            ]
        }

    except Exception as e:
        print(f"[Refiner Agent] Error: {e}")
        return {
            "next_action": "error"
        }


# ============================================================================
# ROUTING FUNCTIONS
# ============================================================================

def critique_router(state: VerificationState) -> Literal["approve", "revise", "reject"]:
    """
    Route based on critic assessment.
    """
    critique = state.get("critique_results", {})
    recommendation = critique.get("recommendation", "approve")

    print(f"[Critique Router] → {recommendation}")
    return recommendation


def grading_router(state: VerificationState) -> Literal["complete", "refine", "new_approach", "max_iterations"]:
    """
    Route based on grader assessment and termination conditions.
    """
    # Check hard limits
    if state["iteration"] >= state.get("max_iterations", 50):
        print(f"[Grading Router] → max_iterations")
        return "max_iterations"

    if state.get("valid_iterations", 0) >= state.get("max_valid_iter", 20):
        print(f"[Grading Router] → max_iterations (valid)")
        return "max_iterations"

    # Check coverage goal
    sim_results = state.get("simulation_results", {})
    if sim_results.get("coverage", 0) >= 100.0:
        print(f"[Grading Router] → complete (100% coverage)")
        return "complete"

    # Check grader recommendation
    grading = state.get("grading_results", {})
    if not grading.get("continue_iteration", True):
        print(f"[Grading Router] → new_approach (grader says stop)")
        return "new_approach"

    # Check for plateau (stuck)
    coverage_history = state.get("coverage_history", [])
    if len(coverage_history) >= 3:
        recent = coverage_history[-3:]
        if max(recent) - min(recent) < 1.0:  # Less than 1% improvement
            print(f"[Grading Router] → new_approach (plateau detected)")
            return "new_approach"

    # Normal refinement
    print(f"[Grading Router] → refine")
    return "refine"


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

def create_verification_graph(llm_backend, simulator, args) -> StateGraph:
    """
    Creates the LangGraph for verification workflow.
    """
    # Create graph
    workflow = StateGraph(VerificationState)

    # Wrap agent functions with dependencies
    async def planner(state):
        return await planner_agent(state, llm_backend)

    async def generator(state):
        return await generator_agent(state, llm_backend)

    async def critic(state):
        return await critic_agent(state, llm_backend)

    def simulator_wrapped(state):
        return simulator_node(state, simulator)

    async def grader(state):
        return await grader_agent(state, llm_backend)

    async def refiner(state):
        return await refiner_agent(state, llm_backend)

    # Add nodes
    workflow.add_node("planner", planner)
    workflow.add_node("generator", generator)
    workflow.add_node("critic", critic)
    workflow.add_node("simulator", simulator_wrapped)
    workflow.add_node("grader", grader)
    workflow.add_node("refiner", refiner)

    # Define edges
    workflow.set_entry_point("planner")

    # Planner → Generator (always)
    workflow.add_edge("planner", "generator")

    # Generator → Critic (always)
    workflow.add_edge("generator", "critic")

    # Critic → conditional routing
    workflow.add_conditional_edges(
        "critic",
        critique_router,
        {
            "approve": "simulator",      # Good quality, simulate
            "revise": "refiner",         # Minor issues, refine
            "reject": "generator"        # Major issues, regenerate
        }
    )

    # Simulator → Grader (always)
    workflow.add_edge("simulator", "grader")

    # Grader → conditional routing
    workflow.add_conditional_edges(
        "grader",
        grading_router,
        {
            "complete": END,             # Done!
            "refine": "refiner",         # Continue refinement
            "new_approach": "generator", # Try fresh approach
            "max_iterations": END        # Hit limit
        }
    )

    # Refiner → Critic (loop back)
    workflow.add_edge("refiner", "critic")

    # Compile graph
    app = workflow.compile()

    return app


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def parse_json_from_response(response: str) -> dict:
    """Extract JSON from LLM response."""
    import re

    # Try to find JSON block
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return {}


def parse_testbench_response(response: str) -> dict:
    """Parse testbench JSON response."""
    parsed = parse_json_from_response(response)
    return {
        "test_bench": parsed.get("test bench", ""),
        "comments": parsed.get("comments", "")
    }


def build_critique_prompt(design_spec: str, code: str, plan: dict) -> str:
    """Build prompt for critic agent."""
    return f"""You are an expert SystemVerilog verification engineer performing code review.

Design Specification:
{design_spec}

Generated Testbench Code:
```systemverilog
{code}
```

Perform a thorough review and identify:
1. Syntax issues and potential compilation errors
2. Missing components (clock, reset, $finish, etc.)
3. Randomization quality and effectiveness
4. Simulation risks (infinite loops, timeouts)
5. Best practices and improvements

Return JSON:
{{
  "critique_score": <0-100>,
  "issues": [{{"severity": "critical|warning|info", "description": "...", "suggestion": "..."}}],
  "recommendation": "approve|revise|reject",
  "reasoning": "..."
}}

Score guidance: 90-100=approve, 70-89=approve/revise, 50-69=revise, <50=reject
"""


def build_grading_prompt(design_spec: str, code: str, sim_results: dict, max_cov: float, history: List[float]) -> str:
    """Build prompt for grader agent."""
    return f"""You are a verification quality grading expert analyzing testbench effectiveness.

Design Specification:
{design_spec}

Simulation Results:
- Success: {sim_results.get('success')}
- Current Coverage: {sim_results.get('coverage')}%
- Maximum Achieved: {max_cov}%
- History: {history[-5:]}

Coverage Feedback:
{sim_results.get('coverage_feedback', 'N/A')}

Analyze and grade:
1. Coverage achievement and progress
2. Test diversity and corner cases
3. Quality of coverage strategy
4. Improvement trajectory

Return JSON:
{{
  "overall_grade": "A|B|C|D|F",
  "quality_score": <0-100>,
  "coverage_score": <0-100>,
  "diversity_score": <0-100>,
  "gap_analysis": "...",
  "specific_improvements": ["...", "..."],
  "continue_iteration": true|false,
  "reasoning": "..."
}}
"""


def build_refinement_prompt(state: VerificationState) -> str:
    """Build prompt for refinement based on current state."""
    sim_results = state.get("simulation_results", {})

    if sim_results.get("success"):
        # Coverage-based refinement
        return iter_prompt(
            coverage_summary=sim_results.get("coverage_summary", ""),
            coverage_feedback=sim_results.get("coverage_feedback", ""),
            previous_testbench=state.get("current_testbench", "")
        )
    else:
        # Error-based refinement
        return error_prompt(
            error_code=sim_results.get("error_code", 0),
            error_message=sim_results.get("error_message", "")
        )


def build_refinement_prompt_with_feedback(state: VerificationState) -> str:
    """Build enhanced refinement prompt with multi-agent feedback."""
    base_prompt = build_refinement_prompt(state)

    # Add critic feedback
    critique = state.get("critique_results", {})
    if critique:
        base_prompt += f"\n\nCritic Review:\n{json.dumps(critique, indent=2)}"

    # Add grader feedback
    grading = state.get("grading_results", {})
    if grading:
        base_prompt += f"\n\nGrader Assessment:\n{json.dumps(grading, indent=2)}"

    return base_prompt


def get_adaptive_temperature(state: VerificationState) -> float:
    """Calculate adaptive temperature based on progress."""
    coverage_history = state.get("coverage_history", [])

    if len(coverage_history) < 2:
        return 0.7  # Default

    # Check improvement
    improvement = coverage_history[-1] - coverage_history[-2]

    if improvement > 5.0:
        return 0.6  # Making progress, be consistent
    elif improvement < 1.0:
        return 0.9  # Stuck, try something different
    else:
        return 0.7  # Normal


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

async def main_example():
    """
    Example usage of the LangGraph verification framework.
    """
    # Mock dependencies (replace with actual implementations)
    from llm_verif.environment import Environment
    from llm_verif.openai_backend import OpenAIBackend
    from llm_verif.questasim import QuestaSim

    # Load environment
    # env = Environment(args)

    # Create LLM backend
    # llm_backend = OpenAIBackend(args)

    # Create simulator
    # simulator = QuestaSim(env, args)

    # Create graph
    # graph = create_verification_graph(llm_backend, simulator, args)

    # Initial state
    initial_state = {
        "design_spec": "Simple 4-bit counter with reset",
        "module_header": "module counter(input clk, rst, output [3:0] count);",
        "design_files": [],
        "messages": [],
        "verification_plan": {},
        "plan_available": False,
        "skip_planning": False,
        "current_testbench": "",
        "current_testbench_comments": "",
        "generated_testbenches": [],
        "generation_count": 0,
        "batch_candidates": [],
        "critique_results": {},
        "simulation_results": {},
        "grading_results": {},
        "iteration": 0,
        "valid_iterations": 0,
        "max_coverage": 0.0,
        "coverage_history": [],
        "max_iterations": 10,
        "max_valid_iter": 5,
        "batch_size": 1,
        "temperature": 0.7,
        "next_action": "continue"
    }

    # Run graph
    # config = {"configurable": {"thread_id": "counter_test_1"}}

    # Stream execution
    # async for event in graph.astream(initial_state, config):
    #     node_name = list(event.keys())[0]
    #     node_state = event[node_name]
    #     print(f"\n{'='*60}")
    #     print(f"Node: {node_name}")
    #     print(f"Iteration: {node_state.get('iteration', 0)}")
    #     print(f"Coverage: {node_state.get('simulation_results', {}).get('coverage', 0)}%")

    # # Get final state
    # final_state = await graph.ainvoke(initial_state, config)
    # print(f"\n{'='*60}")
    # print(f"FINAL RESULTS:")
    # print(f"Max Coverage: {final_state['max_coverage']}%")
    # print(f"Total Iterations: {final_state['iteration']}")
    # print(f"Valid Iterations: {final_state['valid_iterations']}")

    print("Proof of concept structure complete!")
    print("See LANGGRAPH_MIGRATION_STRATEGY.md for implementation details.")


if __name__ == "__main__":
    asyncio.run(main_example())
