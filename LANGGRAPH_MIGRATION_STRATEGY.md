# LangGraph Migration Strategy: Multi-Agent Verification Framework

## Executive Summary

This document outlines a comprehensive strategy to migrate the current linear pipeline-based verification framework to a **LangGraph-based multi-agent system** with specialized agents for planning, generation, criticism, grading, and refinement.

---

## Current Architecture Analysis

### Strengths
- ✅ Async-ready with AsyncOpenAI backend
- ✅ Token-aware conversation management
- ✅ Coverage-driven feedback loops
- ✅ Modular simulator abstraction
- ✅ Rich metrics tracking

### Limitations
- ❌ Linear pipeline with hardcoded stages (plan → generate → iterate)
- ❌ No parallel exploration of test strategies
- ❌ Single LLM handles all tasks (planning, generation, refinement)
- ❌ No quality assessment beyond coverage metrics
- ❌ Limited error recovery strategies
- ❌ Context pruning is manual via stack pointers

---

## LangGraph Migration Vision

### Architecture Transformation

**Current Flow:**
```
System Prompt → [Plan] → Generate TB → Simulate → [Iterate: Refine → Simulate] → Done
```

**Proposed LangGraph Flow:**
```
                    ┌──────────────┐
                    │   Planner    │
                    │   Agent      │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  Generator   │
                    │   Agent      │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──────┐ ┌──▼──────┐ ┌──▼────────┐
       │   Critic    │ │  Grader │ │ Simulator │
       │   Agent     │ │  Agent  │ │           │
       └──────┬──────┘ └──┬──────┘ └──┬────────┘
              │            │            │
              └────────────┼────────────┘
                           │
                    ┌──────▼────────┐
                    │   Decision    │
                    │   Router      │
                    └──────┬────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──────┐ ┌──▼──────┐ ┌──▼────┐
       │  Refiner    │ │ Complete │ │ Retry │
       │  Agent      │ │          │ │       │
       └─────────────┘ └──────────┘ └───────┘
```

---

## Agent Definitions

### 1. **Planner Agent**
**Purpose:** Generate high-level verification strategy and test plan

**Responsibilities:**
- Analyze design specification and coverage goals
- Create structured verification plan with test scenarios
- Identify critical paths, edge cases, and coverage objectives
- Output: JSON verification plan with priorities

**LLM Configuration:**
- Temperature: 0.7 (creative planning)
- Model: GPT-4 or equivalent (reasoning-heavy)
- Prompt: `verification_plan_prompt()` from templates

**State Updates:**
```python
{
  "verification_plan": {
    "objectives": [...],
    "scenarios": [...],
    "priorities": [...],
    "coverage_targets": [...]
  },
  "plan_available": True
}
```

---

### 2. **Generator Agent**
**Purpose:** Generate SystemVerilog testbenches from specifications/plans

**Responsibilities:**
- Create initial testbench from design spec + verification plan
- Generate refined testbenches based on feedback
- Implement randomization and constrained-random testing
- Output: JSON with `{"test bench": "...", "comments": "..."}`

**LLM Configuration:**
- Temperature: Dynamic (via temperature_function)
- Model: Code-optimized LLM (GPT-4, Claude Sonnet, etc.)
- Prompt: `first_testbench_prompt()` or `iter_prompt()`

**State Updates:**
```python
{
  "generated_testbenches": [
    {"code": "...", "iteration": N, "source": "initial|refined"}
  ],
  "current_testbench": "...",
  "generation_count": N
}
```

**Batch Generation:**
- Generate `batch_size` variants in parallel
- Each variant can be evaluated independently

---

### 3. **Critic Agent** (NEW)
**Purpose:** Pre-simulation quality assessment and code review

**Responsibilities:**
- **Syntax Review:** Check for obvious Verilog/SystemVerilog errors
- **Best Practices:** Verify testbench follows verification patterns
- **Completeness:** Ensure $finish, clock generation, stimulus coverage
- **Randomization Quality:** Assess randomization strategy effectiveness
- **Potential Issues:** Flag timeout risks, infinite loops, missing constraints

**LLM Configuration:**
- Temperature: 0.3 (precise, analytical)
- Model: Code-aware LLM with reasoning
- Prompt Template:
  ```
  You are an expert SystemVerilog verification engineer reviewing testbench code.

  Design Specification: {spec}
  Generated Testbench: {code}

  Analyze the testbench for:
  1. Syntax errors and potential compilation issues
  2. Missing components (clock, reset, $finish, etc.)
  3. Randomization strategy effectiveness
  4. Potential simulation timeouts or infinite loops
  5. Coverage strategy alignment with design

  Return JSON:
  {
    "critique_score": 0-100,
    "issues": [{"severity": "critical|warning|info", "description": "...", "suggestion": "..."}],
    "recommendation": "approve|revise|reject"
  }
  ```

**State Updates:**
```python
{
  "critique_results": {
    "score": 0-100,
    "issues": [...],
    "recommendation": "approve|revise|reject"
  }
}
```

**Benefits:**
- Reduce simulator calls (expensive)
- Catch obvious errors before compilation
- Improve testbench quality over iterations

---

### 4. **Grader Agent** (NEW)
**Purpose:** Post-simulation quality assessment and learning feedback

**Responsibilities:**
- **Coverage Analysis:** Deep analysis of coverage gaps and achievements
- **Test Quality Scoring:** Beyond coverage % - assess test diversity, corner cases
- **Comparative Analysis:** Compare current vs previous iterations
- **Learning Recommendations:** Suggest specific improvements for next iteration
- **Success Criteria:** Determine if goal is met or more iteration needed

**LLM Configuration:**
- Temperature: 0.4 (analytical but slightly creative)
- Model: Reasoning-focused LLM
- Prompt Template:
  ```
  You are a verification grading expert analyzing testbench results.

  Design Specification: {spec}
  Testbench Code: {code}
  Coverage Report: {coverage_summary}
  Uncovered Paths: {coverage_feedback}
  Previous Best Coverage: {max_coverage}

  Analyze and grade:
  1. Coverage achievement (current: {total_coverage}%)
  2. Test diversity and corner case coverage
  3. Improvement over previous iterations
  4. Quality of coverage strategy
  5. Remaining gaps and difficulty assessment

  Return JSON:
  {
    "overall_grade": "A|B|C|D|F",
    "quality_score": 0-100,
    "coverage_score": 0-100,
    "diversity_score": 0-100,
    "gap_analysis": "...",
    "specific_improvements": [...],
    "continue_iteration": true|false,
    "reason": "..."
  }
  ```

**State Updates:**
```python
{
  "grading_results": {
    "grade": "A-F",
    "scores": {...},
    "gap_analysis": "...",
    "improvements": [...],
    "continue": bool
  },
  "iteration_history": [...]
}
```

**Benefits:**
- Richer feedback than coverage % alone
- Identify when testbench is "stuck" (diminishing returns)
- Provide targeted guidance for refinement

---

### 5. **Simulator Node**
**Purpose:** Execute testbench and collect coverage (existing system)

**Responsibilities:**
- Compile testbench with design files
- Run simulation with coverage instrumentation
- Parse coverage reports
- Return `CoverageResponse` with metrics

**Configuration:**
- Uses existing `Simulator` abstraction (QuestaSim/Verilator)
- No LLM required (deterministic execution)

**State Updates:**
```python
{
  "simulation_results": {
    "success": bool,
    "error_code": int,
    "coverage": float,
    "coverage_list": [...],
    "error_message": "..."
  }
}
```

---

### 6. **Refiner Agent**
**Purpose:** Targeted improvements based on critic + grader + simulator feedback

**Responsibilities:**
- Synthesize feedback from Critic, Grader, and Simulator
- Apply targeted fixes (compilation errors, coverage gaps)
- Maintain testbench coherence across iterations
- Choose refinement strategy (modify existing vs fresh generation)

**LLM Configuration:**
- Temperature: Dynamic (lower for fixes, higher for new approaches)
- Model: Code-optimized LLM
- Prompt: Enhanced `iter_prompt()` with multi-agent feedback

**Prompt Template:**
```
You are refining a testbench based on comprehensive feedback.

Previous Testbench: {code}

Feedback Sources:
1. Critic Review: {critique}
2. Grader Assessment: {grading}
3. Simulator Results: {coverage_summary}
4. Uncovered Paths: {coverage_feedback}

Choose refinement strategy:
- If critic found critical issues → fix those first
- If coverage gaps identified → add stimulus for uncovered paths
- If stuck at plateau → try different randomization strategy
- If timeout/errors → simplify or restructure

Return JSON: {"test bench": "...", "comments": "...", "strategy": "..."}
```

**State Updates:**
```python
{
  "refinement_strategy": "fix_errors|add_coverage|new_approach|simplify",
  "current_testbench": "...",
  "iteration": N
}
```

---

### 7. **Decision Router** (Conditional Edge Logic)
**Purpose:** Graph flow control based on state

**Routing Logic:**
```python
def route_decision(state: GraphState) -> str:
    # Early termination checks
    if state["iteration"] >= MAX_ITERATIONS:
        return "complete"

    if state["simulation_results"]["coverage"] >= 100:
        return "complete"

    if state["valid_iterations"] >= MAX_VALID_ITER:
        return "complete"

    # Quality-based routing
    critique = state.get("critique_results", {})
    if critique.get("recommendation") == "reject":
        return "refine"  # Skip simulation, go straight to refinement

    grading = state.get("grading_results", {})
    if grading.get("continue") == False:
        return "new_approach"  # Stuck, try different strategy

    sim_result = state.get("simulation_results", {})
    if sim_result.get("success") == False:
        if sim_result.get("error_code") in [1, 2, 5]:  # Compilation/sim errors
            return "refine"
        elif sim_result.get("error_code") == 3:  # Timeout
            return "simplify"

    # Normal iteration
    if sim_result.get("coverage", 0) < 100:
        return "refine"

    return "complete"
```

**Benefits:**
- Adaptive flow based on multi-agent feedback
- Avoid wasted simulator calls
- Intelligent retry strategies

---

## LangGraph State Schema

```python
from typing import TypedDict, List, Dict, Any, Annotated
from langgraph.graph import StateGraph, END
import operator

class VerificationState(TypedDict):
    # Design context
    design_spec: str
    module_header: str
    design_files: List[str]

    # Conversation history
    messages: Annotated[List[Dict], operator.add]  # Append-only messages

    # Planning
    verification_plan: Dict[str, Any]
    plan_available: bool

    # Generation
    current_testbench: str
    generated_testbenches: List[Dict]
    generation_count: int
    batch_candidates: List[str]  # For batch generation

    # Critique
    critique_results: Dict[str, Any]

    # Simulation
    simulation_results: Dict[str, Any]

    # Grading
    grading_results: Dict[str, Any]

    # Iteration tracking
    iteration: int
    valid_iterations: int
    max_coverage: float
    coverage_history: List[float]

    # Metrics
    record: Dict[str, Any]  # Record tracking

    # Control flow
    next_action: str  # "refine", "new_approach", "simplify", "complete"
    error_context: str
```

---

## LangGraph Implementation

### Graph Definition

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# Create graph
workflow = StateGraph(VerificationState)

# Add nodes
workflow.add_node("planner", planner_agent)
workflow.add_node("generator", generator_agent)
workflow.add_node("critic", critic_agent)
workflow.add_node("simulator", simulator_node)
workflow.add_node("grader", grader_agent)
workflow.add_node("refiner", refiner_agent)

# Define edges
workflow.set_entry_point("planner")

# Linear flow for initial generation
workflow.add_edge("planner", "generator")
workflow.add_edge("generator", "critic")

# Conditional after critic
workflow.add_conditional_edges(
    "critic",
    critique_router,
    {
        "approve": "simulator",
        "revise": "refiner",
        "reject": "generator"  # Regenerate from scratch
    }
)

# After simulation, grade
workflow.add_edge("simulator", "grader")

# Conditional after grading
workflow.add_conditional_edges(
    "grader",
    grading_router,
    {
        "complete": END,
        "refine": "refiner",
        "new_approach": "generator",
        "max_iterations": END
    }
)

# Refiner loops back to critic
workflow.add_edge("refiner", "critic")

# Compile graph with checkpointing
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)
```

### Node Implementations

```python
async def planner_agent(state: VerificationState) -> VerificationState:
    """Generate verification plan"""
    if state.get("plan_available"):
        return state  # Skip if plan exists

    # Use existing prompt template
    prompt = verification_plan_prompt()

    # Call LLM
    response = await llm_backend.generate_response_async(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )

    # Parse plan
    plan = parse_verification_plan(response)

    return {
        **state,
        "verification_plan": plan,
        "plan_available": True,
        "messages": [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": response}
        ]
    }

async def generator_agent(state: VerificationState) -> VerificationState:
    """Generate testbench code"""
    iteration = state.get("iteration", 0)

    if iteration == 0:
        # Initial generation
        prompt = first_testbench_prompt(
            state["design_spec"],
            state["module_header"],
            state.get("verification_plan")
        )
    else:
        # Refinement generation
        prompt = build_refinement_prompt(state)

    # Batch generation
    batch_size = state.get("batch_size", 1)
    responses = await llm_backend.generate_response_async(
        messages=build_conversation(state) + [{"role": "user", "content": prompt}],
        num_return_sequences=batch_size
    )

    # Parse testbenches
    testbenches = [parse_testbench(r) for r in responses]

    return {
        **state,
        "batch_candidates": [tb["code"] for tb in testbenches],
        "current_testbench": testbenches[0]["code"],
        "generation_count": state.get("generation_count", 0) + 1,
        "messages": [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": responses[0]}
        ]
    }

async def critic_agent(state: VerificationState) -> VerificationState:
    """Review testbench quality"""
    code = state["current_testbench"]

    prompt = build_critique_prompt(
        state["design_spec"],
        code,
        state.get("verification_plan")
    )

    response = await llm_backend.generate_response_async(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    critique = parse_critique(response)

    return {
        **state,
        "critique_results": critique,
        "messages": [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": response}
        ]
    }

def simulator_node(state: VerificationState) -> VerificationState:
    """Run simulation (existing system)"""
    # Use existing Simulator class
    sim_result = simulator.run_simulation_flow(
        state["current_testbench"],
        iteration=state["iteration"]
    )

    return {
        **state,
        "simulation_results": {
            "success": sim_result.success,
            "error_code": sim_result.error_code,
            "coverage": sim_result.total_coverage,
            "coverage_list": sim_result.coverage_list,
            "error_message": sim_result.error_message
        },
        "max_coverage": max(state.get("max_coverage", 0), sim_result.total_coverage),
        "coverage_history": state.get("coverage_history", []) + [sim_result.total_coverage]
    }

async def grader_agent(state: VerificationState) -> VerificationState:
    """Grade testbench results"""
    prompt = build_grading_prompt(
        state["design_spec"],
        state["current_testbench"],
        state["simulation_results"],
        state["max_coverage"],
        state["coverage_history"]
    )

    response = await llm_backend.generate_response_async(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )

    grading = parse_grading(response)

    return {
        **state,
        "grading_results": grading,
        "messages": [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": response}
        ]
    }

async def refiner_agent(state: VerificationState) -> VerificationState:
    """Refine testbench based on feedback"""
    prompt = build_refinement_prompt(
        state["current_testbench"],
        state.get("critique_results"),
        state.get("grading_results"),
        state.get("simulation_results")
    )

    response = await llm_backend.generate_response_async(
        messages=build_conversation(state) + [{"role": "user", "content": prompt}],
        temperature=get_dynamic_temperature(state["iteration"])
    )

    testbench = parse_testbench(response)

    return {
        **state,
        "current_testbench": testbench["code"],
        "iteration": state["iteration"] + 1,
        "valid_iterations": state.get("valid_iterations", 0) + (1 if state["simulation_results"]["success"] else 0),
        "messages": [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": response}
        ]
    }
```

### Routing Functions

```python
def critique_router(state: VerificationState) -> str:
    """Route based on critic assessment"""
    critique = state.get("critique_results", {})
    recommendation = critique.get("recommendation", "approve")

    if recommendation == "reject":
        return "reject"
    elif recommendation == "revise":
        return "revise"
    else:
        return "approve"

def grading_router(state: VerificationState) -> str:
    """Route based on grader assessment"""
    # Check termination conditions
    if state["iteration"] >= state.get("max_iterations", 50):
        return "max_iterations"

    if state["simulation_results"]["coverage"] >= 100:
        return "complete"

    if state["valid_iterations"] >= state.get("max_valid_iter", 20):
        return "max_iterations"

    # Check grader recommendation
    grading = state.get("grading_results", {})
    if grading.get("continue") == False:
        return "new_approach"

    # Check if stuck (no improvement over 3 iterations)
    coverage_history = state.get("coverage_history", [])
    if len(coverage_history) >= 3:
        recent = coverage_history[-3:]
        if max(recent) - min(recent) < 1.0:  # Less than 1% improvement
            return "new_approach"

    return "refine"
```

---

## Advanced Features

### 1. **Parallel Batch Evaluation**
```python
async def batch_simulator_node(state: VerificationState) -> VerificationState:
    """Simulate all batch candidates in parallel"""
    candidates = state["batch_candidates"]

    # Run simulations in parallel
    sim_tasks = [
        simulator.run_simulation_flow_async(tb, state["iteration"])
        for tb in candidates
    ]
    results = await asyncio.gather(*sim_tasks)

    # Select best coverage
    best_result = max(results, key=lambda r: r.total_coverage)
    best_idx = results.index(best_result)

    return {
        **state,
        "current_testbench": candidates[best_idx],
        "simulation_results": dataclass_to_dict(best_result),
        "batch_results": [dataclass_to_dict(r) for r in results]
    }
```

### 2. **Human-in-the-Loop Node**
```python
def human_review_node(state: VerificationState) -> VerificationState:
    """Optional human review at critical points"""
    if state.get("require_human_review"):
        print(f"Coverage: {state['simulation_results']['coverage']}%")
        print(f"Iteration: {state['iteration']}")
        print(f"Grading: {state['grading_results']['grade']}")

        action = input("Continue? (yes/no/modify): ")

        if action == "no":
            state["next_action"] = "complete"
        elif action == "modify":
            suggestion = input("Provide guidance: ")
            state["human_feedback"] = suggestion

    return state
```

### 3. **Multi-Model Ensemble**
```python
async def ensemble_generator(state: VerificationState) -> VerificationState:
    """Use multiple LLMs and ensemble results"""
    prompt = build_generation_prompt(state)

    # Call multiple models in parallel
    gpt4_response = await gpt4_backend.generate_response_async(messages, temp=0.7)
    claude_response = await claude_backend.generate_response_async(messages, temp=0.7)
    llama_response = await llama_backend.generate_response_async(messages, temp=0.7)

    candidates = [
        parse_testbench(gpt4_response),
        parse_testbench(claude_response),
        parse_testbench(llama_response)
    ]

    return {
        **state,
        "batch_candidates": [c["code"] for c in candidates],
        "ensemble_used": True
    }
```

### 4. **Adaptive Temperature Scheduling**
```python
def adaptive_temperature_node(state: VerificationState) -> VerificationState:
    """Adjust temperature based on progress"""
    coverage_history = state.get("coverage_history", [])

    if len(coverage_history) < 2:
        temperature = 0.7  # Moderate creativity
    else:
        improvement = coverage_history[-1] - coverage_history[-2]
        if improvement > 5.0:
            temperature = 0.6  # Making progress, be consistent
        elif improvement < 1.0:
            temperature = 0.9  # Stuck, try something different
        else:
            temperature = 0.7  # Normal

    return {
        **state,
        "temperature": temperature
    }
```

---

## Migration Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Install LangGraph dependencies
- [ ] Define `VerificationState` TypedDict
- [ ] Create basic graph structure (Planner → Generator → Simulator)
- [ ] Migrate existing prompt templates to node functions
- [ ] Implement simple routing logic
- [ ] Test with single design (e.g., counter)

### Phase 2: Core Agents (Week 3-4)
- [ ] Implement Critic Agent with prompt engineering
- [ ] Implement Grader Agent with prompt engineering
- [ ] Add conditional routing based on critic/grader feedback
- [ ] Integrate with existing Simulator abstraction
- [ ] Test multi-agent flow with 3-5 designs

### Phase 3: Refiner & Advanced Routing (Week 5-6)
- [ ] Implement Refiner Agent with multi-feedback synthesis
- [ ] Add adaptive routing (stuck detection, error recovery)
- [ ] Implement batch evaluation with parallel simulation
- [ ] Add temperature scheduling based on progress
- [ ] Test on full benchmark suite

### Phase 4: Optimization & Features (Week 7-8)
- [ ] Add LangGraph checkpointing for resume capability
- [ ] Implement conversation pruning in state management
- [ ] Add human-in-the-loop optional nodes
- [ ] Optimize token usage with streaming
- [ ] Benchmark performance vs baseline

### Phase 5: Advanced Features (Week 9-10)
- [ ] Multi-model ensemble generation
- [ ] Parallel run execution with LangGraph
- [ ] Enhanced metrics dashboard with agent-level tracking
- [ ] A/B testing framework for agent prompts
- [ ] Documentation and examples

---

## Benefits of LangGraph Migration

### 1. **Modularity**
- Each agent is independently testable
- Easy to swap LLM models per agent
- Clear separation of concerns

### 2. **Flexibility**
- Dynamic routing based on state
- Easy to add new agents (e.g., Security Checker, Power Analysis)
- Conditional execution paths

### 3. **Observability**
- LangGraph provides built-in tracing (LangSmith integration)
- State inspection at each node
- Debug individual agent decisions

### 4. **Scalability**
- Parallel batch evaluation
- Async-native execution
- Checkpointing for long-running jobs

### 5. **Quality**
- Multi-agent feedback improves testbench quality
- Critic reduces wasted simulator calls
- Grader provides richer learning signal

### 6. **Experimentation**
- Easy to A/B test different agent prompts
- Compare routing strategies
- Measure agent contribution to coverage

---

## File Structure Proposal

```
llm_verif/
├── langgraph_framework/
│   ├── __init__.py
│   ├── graph.py              # Main graph definition
│   ├── state.py              # VerificationState schema
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── planner.py        # Planner agent
│   │   ├── generator.py      # Generator agent
│   │   ├── critic.py         # Critic agent (NEW)
│   │   ├── grader.py         # Grader agent (NEW)
│   │   ├── refiner.py        # Refiner agent
│   │   └── base.py           # Base agent class
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── simulator.py      # Simulator node wrapper
│   │   └── human.py          # Human-in-the-loop node
│   ├── routing/
│   │   ├── __init__.py
│   │   ├── critique_router.py
│   │   └── grading_router.py
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── critic_prompts.py
│   │   └── grader_prompts.py
│   └── utils/
│       ├── __init__.py
│       ├── parsers.py        # JSON parsing utilities
│       └── metrics.py        # Agent-level metrics
├── llm_verif_langgraph.py    # New main entry point
└── [existing files...]
```

---

## Example Usage

```python
# llm_verif_langgraph.py

import asyncio
from langgraph_framework.graph import create_verification_graph
from llm_verif.environment import Environment
from llm_verif.simulator import get_simulator

async def main():
    # Load environment
    env = Environment(args)

    # Create graph
    graph = create_verification_graph(
        llm_backend=env.llm,
        simulator=get_simulator(args.simulator),
        args=args
    )

    # Initial state
    initial_state = {
        "design_spec": env.design_specification,
        "module_header": env.module_header,
        "design_files": env.all_design_file_paths,
        "iteration": 0,
        "valid_iterations": 0,
        "max_coverage": 0.0,
        "messages": [],
        "plan_available": not args.testplan  # Skip planning if disabled
    }

    # Run graph
    config = {"configurable": {"thread_id": f"{args.design}_{args.id}"}}

    async for state in graph.astream(initial_state, config):
        print(f"Node: {state.keys()}")
        print(f"Coverage: {state.get('simulation_results', {}).get('coverage', 0)}%")

    # Final state
    final_state = await graph.ainvoke(initial_state, config)
    print(f"Final Coverage: {final_state['max_coverage']}%")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Prompt Engineering Examples

### Critic Prompt Template
```python
def build_critique_prompt(design_spec: str, testbench_code: str, plan: dict) -> str:
    return f"""You are an expert SystemVerilog verification engineer performing code review.

Design Specification:
{design_spec}

Verification Plan Objectives:
{json.dumps(plan.get('objectives', []), indent=2)}

Generated Testbench Code:
```systemverilog
{testbench_code}
```

Perform a thorough review and identify:

1. **Syntax Issues**: Potential compilation errors, typos, missing semicolons
2. **Completeness**: Missing required components:
   - Clock generation
   - Reset sequence
   - Test stimulus
   - $finish statement (to prevent timeout)
   - Output monitoring
3. **Randomization Quality**:
   - Are random variables properly seeded?
   - Is randomization range appropriate for design?
   - Are constraints necessary but missing?
4. **Simulation Risks**:
   - Infinite loops or timeout potential
   - Insufficient test duration
   - Missing edge cases from verification plan
5. **Best Practices**:
   - Clear signal naming
   - Adequate comments
   - Reusable structure

Severity Levels:
- **critical**: Will cause compilation/simulation failure or timeout
- **warning**: Suboptimal but may work
- **info**: Suggestions for improvement

Return ONLY valid JSON in this exact format:
{{
  "critique_score": <0-100 integer>,
  "issues": [
    {{"severity": "critical|warning|info", "description": "...", "suggestion": "..."}},
    ...
  ],
  "recommendation": "approve|revise|reject",
  "reasoning": "Brief explanation of recommendation"
}}

Score Guidance:
- 90-100: Excellent, minor suggestions only → approve
- 70-89: Good with some improvements needed → approve or revise
- 50-69: Significant issues → revise
- 0-49: Major problems → reject

Recommendation Guidance:
- **approve**: Ready for simulation (score >= 80, no critical issues)
- **revise**: Fixable issues, refine before simulation (critical or multiple warnings)
- **reject**: Fundamentally flawed, regenerate from scratch (score < 50)
"""
```

### Grader Prompt Template
```python
def build_grading_prompt(
    design_spec: str,
    testbench_code: str,
    sim_results: dict,
    max_coverage: float,
    coverage_history: List[float]
) -> str:
    return f"""You are a verification quality grading expert analyzing testbench effectiveness.

Design Specification:
{design_spec}

Testbench Code:
```systemverilog
{testbench_code}
```

Simulation Results:
- Success: {sim_results['success']}
- Current Coverage: {sim_results['coverage']}%
- Error Code: {sim_results['error_code']}
- Error Message: {sim_results.get('error_message', 'None')}

Coverage Progress:
- Maximum Achieved: {max_coverage}%
- History (last 5): {coverage_history[-5:]}

Coverage Feedback (Uncovered Areas):
{sim_results.get('coverage_feedback', 'N/A')}

Analyze and grade the testbench on multiple dimensions:

1. **Coverage Achievement** (0-100):
   - Current coverage percentage: {sim_results['coverage']}%
   - Progress vs. previous iterations
   - Remaining gap to 100%

2. **Test Diversity** (0-100):
   - Are different test scenarios explored?
   - Does it exercise various input combinations?
   - Are edge cases covered (e.g., min/max values, corner cases)?

3. **Quality of Coverage Strategy** (0-100):
   - Is randomization effective?
   - Does it target uncovered areas intelligently?
   - Is test stimulus appropriate for design complexity?

4. **Improvement Trajectory** (0-100):
   - Is coverage improving over iterations?
   - Rate of improvement (fast/slow/plateaued)
   - Diminishing returns indicator

5. **Gap Analysis**:
   - What specific design areas remain uncovered?
   - Why might they be difficult to reach?
   - Are they reachable with better stimulus or fundamental barriers?

6. **Recommendations**:
   - Should iteration continue or stop?
   - Specific improvements for next iteration
   - Alternative strategies if stuck

Return ONLY valid JSON:
{{
  "overall_grade": "A|B|C|D|F",
  "quality_score": <0-100>,
  "coverage_score": <0-100>,
  "diversity_score": <0-100>,
  "strategy_score": <0-100>,
  "improvement_score": <0-100>,
  "gap_analysis": "Detailed analysis of remaining coverage gaps",
  "specific_improvements": [
    "Concrete suggestion 1",
    "Concrete suggestion 2",
    ...
  ],
  "continue_iteration": true|false,
  "reasoning": "Why continue or stop",
  "plateau_detected": true|false,
  "stuck_reason": "Why testbench may be stuck (if applicable)"
}}

Grading Rubric:
- **A (90-100)**: Excellent coverage (>95%) with diverse, effective tests
- **B (80-89)**: Good coverage (80-95%) with solid strategy
- **C (70-79)**: Moderate coverage (60-80%) with room for improvement
- **D (60-69)**: Low coverage (<60%) but making progress
- **F (<60)**: Poor coverage with little progress

Continue Iteration Guidelines:
- **true**: Coverage < 100%, making progress (>1% improvement in last 2 iterations), not stuck
- **false**: Coverage = 100%, OR stuck (no improvement in last 3 iterations), OR fundamental barrier detected

Plateau Detection:
- Stuck if: coverage improvement < 1% over last 3 iterations AND coverage < 95%
"""
```

---

## Metrics & Observability

### Enhanced Metrics Tracking

```python
@dataclass
class AgentMetrics:
    agent_name: str
    execution_time: float
    tokens_used: int
    success: bool
    output_quality_score: float

class LangGraphRecord(Record):
    """Extended Record class for LangGraph metrics"""

    def add_agent_execution(self, agent: str, metrics: AgentMetrics):
        """Track individual agent performance"""
        self.dataframe = self.dataframe.append({
            'agent_name': agent,
            'execution_time': metrics.execution_time,
            'tokens_used': metrics.tokens_used,
            'success': metrics.success,
            'quality_score': metrics.output_quality_score
        }, ignore_index=True)

    def get_agent_statistics(self) -> pd.DataFrame:
        """Aggregate statistics per agent"""
        return self.dataframe.groupby('agent_name').agg({
            'execution_time': ['mean', 'sum'],
            'tokens_used': ['mean', 'sum'],
            'success': 'mean',
            'quality_score': 'mean'
        })
```

### LangSmith Integration
```python
from langsmith import Client
from langgraph.prebuilt import create_agent_executor

# Enable tracing
import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "your-api-key"

# Automatic tracing of all agent calls
graph = create_verification_graph(...)
```

---

## Testing Strategy

### Unit Tests for Agents
```python
# tests/test_critic_agent.py

import pytest
from langgraph_framework.agents.critic import critic_agent

@pytest.mark.asyncio
async def test_critic_rejects_invalid_testbench():
    state = {
        "design_spec": "Simple counter",
        "current_testbench": "module invalid_syntax  // missing everything",
        "verification_plan": {}
    }

    result = await critic_agent(state)

    assert result["critique_results"]["recommendation"] == "reject"
    assert result["critique_results"]["critique_score"] < 50
    assert any(issue["severity"] == "critical" for issue in result["critique_results"]["issues"])

@pytest.mark.asyncio
async def test_critic_approves_valid_testbench():
    state = {
        "design_spec": load_fixture("counter_spec.txt"),
        "current_testbench": load_fixture("good_counter_tb.sv"),
        "verification_plan": {}
    }

    result = await critic_agent(state)

    assert result["critique_results"]["recommendation"] == "approve"
    assert result["critique_results"]["critique_score"] >= 80
```

### Integration Tests
```python
# tests/test_langgraph_integration.py

@pytest.mark.asyncio
async def test_full_graph_execution():
    graph = create_verification_graph(mock_llm, mock_simulator, args)

    initial_state = create_test_state("counter")

    final_state = await graph.ainvoke(initial_state)

    assert final_state["max_coverage"] > 0
    assert final_state["iteration"] > 0
    assert "grading_results" in final_state
```

---

## Conclusion

This migration strategy transforms the linear pipeline into a **sophisticated multi-agent system** with:

1. ✅ **Specialized Agents**: Planner, Generator, Critic, Grader, Refiner
2. ✅ **Intelligent Routing**: Adaptive flow based on quality assessment
3. ✅ **Rich Feedback**: Multi-dimensional evaluation beyond coverage
4. ✅ **Efficiency**: Reduced simulator calls via pre-simulation critique
5. ✅ **Observability**: LangGraph tracing and agent-level metrics
6. ✅ **Flexibility**: Easy to experiment with prompts, models, routing
7. ✅ **Scalability**: Parallel execution, checkpointing, async-native

**Next Steps:**
1. Review and approve strategy
2. Begin Phase 1 implementation
3. Set up metrics dashboard for A/B testing
4. Iterate based on benchmark results

---

**Document Version:** 1.0
**Last Updated:** 2025-11-03
**Author:** Claude (Sonnet 4.5)
