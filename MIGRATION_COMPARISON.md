# Current vs. LangGraph Architecture: Detailed Comparison

## Overview

This document provides a side-by-side comparison of your current linear pipeline architecture with the proposed LangGraph multi-agent system, showing exactly how each component maps and transforms.

---

## Architecture Comparison

### Current Architecture (Linear Pipeline)

```
ConversationRunner.run_conversation()
    │
    ├─ Initialize ConversationManager (token-aware context)
    │
    ├─ Stage 1: Optional Testplan Generation
    │   └─ generate_and_evaluate(testplan_prompt, json=False)
    │
    ├─ Stage 2: Initial Testbench Generation
    │   └─ generate_and_evaluate(testbench_prompt, batch_size)
    │       ├─ LLM generates batch_size testbenches
    │       ├─ Parse JSON responses
    │       ├─ Simulate ALL successful testbenches
    │       └─ Select best coverage, append to conversation
    │
    └─ Stage 3: Iterative Refinement Loop
        └─ while (coverage < 100 AND iter < max_iter AND valid_iter < max_valid)
            ├─ Build prompt: error_prompt() OR iter_prompt()
            ├─ generate_and_evaluate(prompt, batch_size)
            └─ Update conversation with best result
```

**Key Characteristics:**
- ✅ Sequential execution (await each stage)
- ✅ Batch generation with best-selection
- ✅ Token-aware context pruning via `ConversationManager`
- ✅ Stack pointer for context slicing
- ❌ No quality assessment before simulation
- ❌ Single termination criteria (coverage/iterations)
- ❌ Limited feedback (only coverage metrics)

---

### Proposed Architecture (LangGraph Multi-Agent)

```
LangGraph State Machine
    │
    ├─ Planner Agent (optional)
    │   └─ Generate verification plan
    │
    ├─ Generator Agent
    │   └─ Generate testbench(es)
    │
    ├─ Critic Agent (NEW) ◄─┐
    │   ├─ Pre-simulation review  │
    │   └─ Route: approve/revise/reject
    │       ├─ approve → Simulator
    │       ├─ revise → Refiner ────┘
    │       └─ reject → Generator
    │
    ├─ Simulator Node
    │   └─ Execute testbench, collect coverage
    │
    ├─ Grader Agent (NEW)
    │   ├─ Multi-dimensional assessment
    │   └─ Route: complete/refine/new_approach/max_iter
    │       ├─ complete → END
    │       ├─ refine → Refiner ───┐
    │       ├─ new_approach → Generator
    │       └─ max_iter → END
    │
    └─ Refiner Agent
        ├─ Synthesize multi-agent feedback
        └─ Generate improved testbench → Critic ┘
```

**Key Characteristics:**
- ✅ Directed acyclic graph with conditional routing
- ✅ Pre-simulation quality gates (Critic)
- ✅ Multi-dimensional feedback (Critic + Grader + Simulator)
- ✅ Adaptive routing based on state
- ✅ Built-in tracing and observability
- ✅ Checkpointing for resume capability
- ✅ Parallel exploration potential

---

## Component Mapping

### 1. ConversationManager → LangGraph State

#### Current: ConversationManager
```python
class ConversationManager:
    def __init__(self, tokenizer, system_prompt, max_input_tokens=15000):
        self.conversation = [{"role": "system", "content": system_prompt}]
        self.stack_pointer = 1
        self.max_input_tokens = max_input_tokens

    def append_user_message(self, message, update_stack_pointer=False)
    def append_assistant_message(self, message, slice=False)
    def slice_from_stack_pointer()  # Remove intermediate messages
    def get_messages()  # Returns pruned conversation
```

**Responsibilities:**
- Message history management
- Token counting and pruning
- Context slicing via stack pointer

#### LangGraph: State + Message History

```python
class VerificationState(TypedDict):
    # Messages stored in state (append-only with operator.add)
    messages: Annotated[List[Dict[str, str]], operator.add]

    # Additional state fields
    iteration: int
    max_coverage: float
    simulation_results: Dict[str, Any]
    critique_results: Dict[str, Any]
    grading_results: Dict[str, Any]
    ...
```

**Migration Path:**
1. **Message History**: Store in `state["messages"]` with `Annotated[List, operator.add]`
2. **Token Pruning**: Implement as utility function that filters `state["messages"]`
3. **Context Slicing**: Use message indexing in state instead of stack pointer

**Example Migration:**
```python
# BEFORE (Current)
conversation.append_user_message(prompt, update_stack_pointer=True)
conversation.append_assistant_message(response, slice=True)

# AFTER (LangGraph)
def generator_agent(state: VerificationState) -> Dict:
    # Add messages to state (automatically appended)
    return {
        "messages": [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": response}
        ]
    }

# Token pruning utility
def prune_messages(messages: List[Dict], max_tokens: int) -> List[Dict]:
    tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-3.3-70B-Instruct")

    # Keep system prompt + recent messages that fit in max_tokens
    system_msg = messages[0]
    user_assistant_pairs = messages[1:]

    # Count tokens and remove oldest pairs if needed
    while count_tokens(user_assistant_pairs) > max_tokens and len(user_assistant_pairs) > 2:
        user_assistant_pairs = user_assistant_pairs[2:]  # Remove oldest pair

    return [system_msg] + user_assistant_pairs
```

---

### 2. ConversationRunner.generate_and_evaluate() → Multiple Agents

#### Current: Monolithic generate_and_evaluate()
```python
async def generate_and_evaluate(
    self, prompt, run, iteration, json=True,
    batch_size=1, set_stack_pointer=False, sim_runs=1
) -> CoverageResponse:

    # 1. Add prompt to conversation
    self.conversation.append_user_message(prompt, update_stack_pointer=set_stack_pointer)

    # 2. Generate responses (batch)
    responses, tokens, gen_time = await self.llm.generate_response_async(
        self.conversation, num_return_sequences=batch_size
    )

    # 3. Parse JSON
    json_responses = [self.parse_json_response(r) for r in responses]

    # 4. Simulate all successful testbenches
    coverage_responses = [
        self.evaluate_coverage(tb_code, tb_name, run, iteration, i)
        for i, tb_code in enumerate(successful_responses)
    ]

    # 5. Select best coverage
    max_coverage = max(coverage_responses, key=lambda r: r.total_coverage)

    # 6. Append best to conversation
    self.conversation.append_assistant_message(
        max_coverage[1], slice=self.environment.remove_polluted_context
    )

    # 7. Record metrics
    self.record.update_dataframe(...)

    return max_coverage
```

**Issues:**
- ❌ Does everything in one function (generation, simulation, selection, recording)
- ❌ No quality check before simulation
- ❌ Always simulates even if testbench is obviously broken
- ❌ Limited feedback (only coverage %)

#### LangGraph: Split into Multiple Agents

```python
# AGENT 1: Generator (focused on generation only)
async def generator_agent(state: VerificationState, llm) -> Dict:
    prompt = build_prompt_from_state(state)

    responses, tokens, gen_time = await llm.generate_response_async(...)

    testbenches = [parse_testbench(r) for r in responses]

    return {
        "current_testbench": testbenches[0]["code"],
        "batch_candidates": [tb["code"] for tb in testbenches],
        "messages": [...],
        "generation_count": state["generation_count"] + 1
    }

# AGENT 2: Critic (NEW - pre-simulation quality check)
async def critic_agent(state: VerificationState, llm) -> Dict:
    code = state["current_testbench"]

    critique_prompt = build_critique_prompt(code, state["design_spec"])
    critique_response = await llm.generate_response_async(...)
    critique = parse_json(critique_response)

    # Critic can catch errors BEFORE expensive simulation
    return {
        "critique_results": critique  # Used by router
    }

# ROUTER: Decide whether to simulate or skip
def critique_router(state: VerificationState) -> str:
    recommendation = state["critique_results"]["recommendation"]

    if recommendation == "reject":
        return "generator"  # Skip simulation, regenerate
    elif recommendation == "revise":
        return "refiner"    # Skip simulation, fix issues
    else:
        return "simulator"  # Looks good, proceed to simulation

# NODE 3: Simulator (focused on simulation only)
def simulator_node(state: VerificationState, simulator) -> Dict:
    code = state["current_testbench"]

    cov_response = simulator.run_simulation_flow(code, state["iteration"])

    return {
        "simulation_results": {
            "coverage": cov_response.total_coverage,
            "success": cov_response.success,
            ...
        },
        "max_coverage": max(state["max_coverage"], cov_response.total_coverage)
    }

# AGENT 4: Grader (NEW - post-simulation quality assessment)
async def grader_agent(state: VerificationState, llm) -> Dict:
    grading_prompt = build_grading_prompt(
        state["simulation_results"],
        state["coverage_history"],
        state["max_coverage"]
    )

    grading_response = await llm.generate_response_async(...)
    grading = parse_json(grading_response)

    # Rich feedback beyond coverage %
    return {
        "grading_results": grading  # Used by router
    }

# AGENT 5: Refiner (targeted improvements)
async def refiner_agent(state: VerificationState, llm) -> Dict:
    # Synthesize feedback from ALL sources
    feedback = {
        "critique": state.get("critique_results"),
        "grading": state.get("grading_results"),
        "simulation": state.get("simulation_results")
    }

    refinement_prompt = build_refinement_prompt(
        state["current_testbench"],
        feedback
    )

    refined_response = await llm.generate_response_async(...)
    refined_tb = parse_testbench(refined_response)

    return {
        "current_testbench": refined_tb["code"],
        "iteration": state["iteration"] + 1
    }
```

**Benefits:**
- ✅ Separation of concerns (each agent has single responsibility)
- ✅ Pre-simulation quality gates save compute
- ✅ Multi-dimensional feedback improves quality
- ✅ Easier to test and debug individual agents
- ✅ Can swap LLMs per agent (e.g., cheaper model for critique)

---

### 3. Iteration Loop → LangGraph Conditional Routing

#### Current: While Loop with Manual Control
```python
async def run_conversation(self, run_index: int):
    iteration = 0
    valid_iterations = 0
    first_success = True

    # Stage 2: Generate initial testbench
    cov = await self.generate_and_evaluate(testbench_prompt, run_index, iteration, ...)
    if cov.success:
        valid_iterations += 1

    iteration += 1

    # Stage 3: Iterative refinement
    while (self.record.max_cov < 100
           and iteration <= self.args.max_iterations
           and valid_iterations < self.args.max_valid_iter):

        # Determine prompt based on error/success
        if not cov.success:
            prompt = prompt_templates.error_prompt(cov.error_code, cov.error_message)
        else:
            prompt = prompt_templates.iter_prompt(cov, ...)

        cov = await self.generate_and_evaluate(prompt, run_index, iteration, ...)

        iteration += 1
```

**Issues:**
- ❌ Manual state tracking (iteration, valid_iterations)
- ❌ Simple termination criteria (coverage/iterations)
- ❌ No detection of "stuck" state (plateau)
- ❌ Hard to add new routing logic

#### LangGraph: Declarative Conditional Edges

```python
def create_verification_graph(llm, simulator, args):
    workflow = StateGraph(VerificationState)

    # Add nodes
    workflow.add_node("generator", generator_agent)
    workflow.add_node("critic", critic_agent)
    workflow.add_node("simulator", simulator_node)
    workflow.add_node("grader", grader_agent)
    workflow.add_node("refiner", refiner_agent)

    # Define flow
    workflow.set_entry_point("generator")
    workflow.add_edge("generator", "critic")

    # Conditional routing after critic
    workflow.add_conditional_edges(
        "critic",
        critique_router,
        {
            "approve": "simulator",
            "revise": "refiner",
            "reject": "generator"
        }
    )

    workflow.add_edge("simulator", "grader")

    # Conditional routing after grader
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

    workflow.add_edge("refiner", "critic")  # Loop back

    return workflow.compile()


def grading_router(state: VerificationState) -> str:
    """Intelligent routing with multiple criteria"""

    # Hard limits
    if state["iteration"] >= state["max_iterations"]:
        return "max_iterations"

    if state["valid_iterations"] >= state["max_valid_iter"]:
        return "max_iterations"

    # Success criteria
    if state["simulation_results"]["coverage"] >= 100:
        return "complete"

    # Plateau detection (NEW)
    coverage_history = state["coverage_history"]
    if len(coverage_history) >= 3:
        recent = coverage_history[-3:]
        if max(recent) - min(recent) < 1.0:  # Stuck
            return "new_approach"

    # Grader recommendation (NEW)
    if not state["grading_results"].get("continue_iteration", True):
        return "new_approach"

    # Normal refinement
    return "refine"
```

**Benefits:**
- ✅ Declarative flow definition
- ✅ State automatically tracked by LangGraph
- ✅ Easy to add new routing conditions
- ✅ Built-in support for complex decision trees
- ✅ Visualizable graph structure

---

## Key Transformations

### 1. Stack Pointer → Message Indexing

**Current Approach:**
```python
# Set stack pointer at first success
self.conversation.append_user_message(prompt, update_stack_pointer=True)

# Later: slice to remove intermediate messages
self.conversation.append_assistant_message(response, slice=True)

# Result: conversation = [system_prompt, user_msg_at_stack, latest_response]
```

**LangGraph Approach:**
```python
# Option 1: Keep full history, prune when building context
def build_llm_context(state: VerificationState) -> List[Dict]:
    messages = state["messages"]

    if state.get("remove_polluted_context"):
        # Find first successful generation
        first_success_idx = find_first_success_index(messages)
        # Keep: system + first success + recent messages
        return [messages[0]] + messages[first_success_idx:first_success_idx+2] + messages[-2:]
    else:
        # Return pruned full history
        return prune_messages(messages, max_tokens=15000)

# Option 2: Store critical messages separately
class VerificationState(TypedDict):
    messages: List[Dict]  # Full history
    critical_messages: List[Dict]  # First success + latest
```

---

### 2. Batch Generation + Best Selection → Parallel Evaluation

**Current:**
```python
# Generate batch
responses = await llm.generate_response_async(
    conversation, num_return_sequences=batch_size
)

# Simulate ALL sequentially
coverage_responses = [
    self.evaluate_coverage(tb, ...)
    for tb in successful_testbenches
]

# Select best
best = max(coverage_responses, key=lambda r: r.total_coverage)
```

**LangGraph:**
```python
# OPTION 1: Parallel simulation in simulator node
async def parallel_simulator_node(state: VerificationState, simulator) -> Dict:
    candidates = state["batch_candidates"]

    # Simulate in parallel
    sim_tasks = [
        simulator.run_simulation_flow_async(tb, state["iteration"])
        for tb in candidates
    ]
    results = await asyncio.gather(*sim_tasks)

    # Select best
    best_idx = max(range(len(results)), key=lambda i: results[i].total_coverage)

    return {
        "current_testbench": candidates[best_idx],
        "simulation_results": dataclass_to_dict(results[best_idx]),
        "batch_results": [dataclass_to_dict(r) for r in results]
    }

# OPTION 2: Beam search with parallel branches
def create_beam_search_graph():
    # Generate N candidates
    # Fork graph into N parallel paths
    # Each path: Critic → Simulator → Grader
    # Merge paths: Select best based on grader scores
```

---

### 3. Error Handling → Routing + Specialized Agents

**Current:**
```python
if not cov.success:
    prompt = prompt_templates.error_prompt(cov.error_code, cov.error_message)
else:
    prompt = prompt_templates.iter_prompt(cov, ...)
```

**LangGraph:**
```python
def simulation_router(state: VerificationState) -> str:
    sim_results = state["simulation_results"]

    if not sim_results["success"]:
        error_code = sim_results["error_code"]

        if error_code in [1, 2]:  # Compile/sim errors
            return "error_fixer_agent"
        elif error_code == 3:  # Timeout
            return "simplifier_agent"
        elif error_code in [4, 5]:  # JSON/format errors
            return "format_fixer_agent"

    return "grader"  # Success path
```

---

## Migration Checklist

### Phase 1: Setup & Basic Graph
- [ ] Install LangGraph: `pip install langgraph langsmith`
- [ ] Define `VerificationState` TypedDict with all current fields
- [ ] Create basic graph: Planner → Generator → Simulator
- [ ] Migrate `ConversationManager` message logic to state
- [ ] Test with single design

### Phase 2: Add Critic Agent
- [ ] Implement `critic_agent()` with quality check prompt
- [ ] Add `critique_router()` for approve/revise/reject
- [ ] Update graph: Generator → Critic → conditional routing
- [ ] Measure reduction in failed simulations
- [ ] Benchmark: Critic time vs simulation time saved

### Phase 3: Add Grader Agent
- [ ] Implement `grader_agent()` with multi-dimensional assessment
- [ ] Add plateau detection to `grading_router()`
- [ ] Update graph: Simulator → Grader → conditional routing
- [ ] Track grading metrics in Record
- [ ] Compare coverage improvement vs baseline

### Phase 4: Add Refiner Agent
- [ ] Implement `refiner_agent()` with multi-feedback synthesis
- [ ] Create routing loop: Refiner → Critic → [Simulator|Refiner]
- [ ] Test refinement quality vs simple regeneration
- [ ] Add adaptive temperature scheduling

### Phase 5: Optimization
- [ ] Implement parallel batch simulation
- [ ] Add LangGraph checkpointing
- [ ] Optimize token usage with message pruning
- [ ] Add human-in-the-loop option
- [ ] Create visualization dashboard

### Phase 6: Advanced Features
- [ ] Multi-model ensemble (GPT-4, Claude, Llama)
- [ ] Beam search with parallel branches
- [ ] Meta-agent for strategy selection
- [ ] A/B testing framework for prompts

---

## Code Migration Example: Side-by-Side

### Current Code (conversation_runner.py)
```python
async def run_conversation(self, run_index: int):
    # Initialize
    self.conversation = ConversationManager(
        self.tokenizer,
        prompt_templates.system_prompt(
            self.environment.design_specification,
            self.environment.module_header
        )
    )

    iteration = 0
    valid_iterations = 0

    # Generate initial testbench
    testbench_prompt = prompt_templates.first_testbench_prompt(...)
    cov = await self.generate_and_evaluate(
        testbench_prompt, run_index, iteration,
        batch_size=self.environment.batch_size
    )

    if cov.success:
        valid_iterations += 1

    iteration += 1

    # Iterative refinement
    while (self.record.max_cov < 100
           and iteration <= self.args.max_iterations
           and valid_iterations < self.args.max_valid_iter):

        if not cov.success:
            prompt = prompt_templates.error_prompt(cov.error_code, cov.error_message)
        else:
            prompt = prompt_templates.iter_prompt(cov, ...)

        cov = await self.generate_and_evaluate(
            prompt, run_index, iteration,
            batch_size=self.environment.batch_size
        )

        iteration += 1
```

### LangGraph Code (llm_verif_langgraph.py)
```python
async def run_verification(args, environment, llm, simulator):
    # Create graph
    graph = create_verification_graph(llm, simulator, args)

    # Initial state
    initial_state = {
        "design_spec": environment.design_specification,
        "module_header": environment.module_header,
        "design_files": environment.all_design_file_paths,
        "messages": [],
        "iteration": 0,
        "valid_iterations": 0,
        "max_coverage": 0.0,
        "coverage_history": [],
        "max_iterations": args.max_iterations,
        "max_valid_iter": args.max_valid_iter,
        "batch_size": args.batch_size,
        "temperature": args.temperature
    }

    # Execute graph
    config = {"configurable": {"thread_id": f"{args.design}_{args.id}"}}

    # Option 1: Stream events
    async for event in graph.astream(initial_state, config):
        node_name = list(event.keys())[0]
        node_state = event[node_name]
        print(f"[{node_name}] Coverage: {node_state.get('max_coverage', 0)}%")

    # Option 2: Get final state
    final_state = await graph.ainvoke(initial_state, config)

    return final_state
```

**Key Differences:**
1. ✅ No manual loop management
2. ✅ Graph handles routing automatically
3. ✅ State is immutable (functional updates)
4. ✅ Built-in checkpointing support
5. ✅ Easier to add new agents/routing

---

## Performance Comparison

### Estimated Impact

| Metric | Current | LangGraph | Change |
|--------|---------|-----------|--------|
| **Simulator Calls** | N iterations × batch_size | 0.7 × N × batch_size | -30% (Critic catches errors) |
| **Token Usage** | Baseline | 1.2 × Baseline | +20% (Critic/Grader overhead) |
| **Coverage Quality** | Baseline | 1.15 × Baseline | +15% (Better feedback) |
| **Development Time** | Baseline | 1.3 × Baseline | +30% (Initial setup) |
| **Debugging Time** | Baseline | 0.6 × Baseline | -40% (Modular agents) |
| **Extensibility** | Hard | Easy | ✅ Easier to add agents |

### ROI Analysis

**Costs:**
- Initial migration: 3-4 weeks development
- Additional LLM calls: ~20% more tokens (Critic + Grader)
- Learning curve: 1 week for team

**Benefits:**
- Reduced simulator calls: ~30% fewer (expensive)
- Better coverage: ~15% improvement
- Faster debugging: ~40% reduction
- Easier experimentation: 10x faster to test new agents
- Better observability: Built-in tracing

**Break-even:** ~2-3 months for a team running 100+ verification runs/week

---

## Recommendations

### Short-term (Next 2 Weeks)
1. **Proof of Concept**: Implement basic 3-node graph (Generator → Simulator → Refiner)
2. **Baseline Metrics**: Run current system on 10 designs, measure coverage/tokens/time
3. **Single Design Test**: Migrate one design to LangGraph, compare metrics

### Medium-term (Weeks 3-6)
1. **Add Critic Agent**: Implement quality gates, measure simulation reduction
2. **Add Grader Agent**: Implement rich feedback, measure coverage improvement
3. **Full Benchmark**: Run LangGraph on all designs, compare vs baseline

### Long-term (Months 2-3)
1. **Production Migration**: Replace current system with LangGraph
2. **Advanced Features**: Parallel evaluation, multi-model ensemble
3. **Optimization**: Fine-tune prompts, optimize token usage
4. **Documentation**: Write internal guides, train team

---

## Conclusion

The migration from your current linear pipeline to LangGraph provides:

### ✅ Immediate Benefits
- Modular, testable agents
- Pre-simulation quality gates
- Richer feedback loops

### ✅ Strategic Benefits
- Easier experimentation
- Better observability
- Scalable architecture

### ✅ Long-term Benefits
- Research-ready platform
- Publication potential
- Community adoption

**Recommendation**: Start with Phase 1 (basic graph) to validate approach, then incrementally add agents based on measured impact.

---

**Document Version:** 1.0
**Last Updated:** 2025-11-03
**Next Review:** After Phase 1 completion
