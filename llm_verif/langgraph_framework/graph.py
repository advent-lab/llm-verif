"""
LangGraph Construction for Verification Framework

Builds the complete multi-agent verification graph.
"""

import logging
from langgraph.graph import StateGraph, END
from llm_verif.langgraph_framework.state import VerificationState
from llm_verif.langgraph_framework.agents import (
    planner_agent,
    generator_agent,
    critic_agent,
    grader_agent,
    refiner_agent
)
from llm_verif.langgraph_framework.nodes import simulator_node
from llm_verif.langgraph_framework.routing import (
    initial_router,
    critique_router,
    grading_router
)


def create_verification_graph(llm_backend, simulator, environment, args, record=None):
    """
    Create the complete LangGraph for verification workflow.

    Graph Structure:
    ```
                    START
                      ↓
                [initial_router]
                  /        \
            planner      generator ←────────┐
                \          /                │
                generator                   │
                    ↓                       │
                critic                      │
              /    |    \                  │
        approve  revise  reject            │
            ↓       ↓       ↓              │
       simulator  refiner  generator ──────┘
            ↓       ↓
         grader   critic
       /  |  |  \
complete  |  |  refine
          |  |    ↓
          |  new_approach
          |      ↓
    max_iterations  generator
    ```

    Args:
        llm_backend: LLM backend (OpenAIBackend or LlamaChat)
        simulator: Simulator instance (QuestaSim or Verilator)
        environment: Environment with design info
        args: Command-line arguments

    Returns:
        Compiled LangGraph application
    """
    logging.info("[Graph] Building LangGraph verification workflow...")

    # Create state graph
    workflow = StateGraph(VerificationState)

    # ========================================================================
    # WRAP AGENTS WITH DEPENDENCIES
    # ========================================================================

    async def planner(state):
        return await planner_agent(state, llm_backend)

    async def generator(state):
        return await generator_agent(state, llm_backend, environment)

    async def critic(state):
        return await critic_agent(state, llm_backend)

    def simulator_wrapped(state):
        return simulator_node(state, simulator, environment, record)

    async def grader(state):
        return await grader_agent(state, llm_backend)

    async def refiner(state):
        return await refiner_agent(state, llm_backend, environment)

    # ========================================================================
    # ADD NODES
    # ========================================================================

    workflow.add_node("planner", planner)
    workflow.add_node("generator", generator)
    workflow.add_node("critic", critic)
    workflow.add_node("simulator", simulator_wrapped)
    workflow.add_node("grader", grader)
    workflow.add_node("refiner", refiner)

    logging.info("[Graph] Added 6 nodes: planner, generator, critic, simulator, grader, refiner")

    # ========================================================================
    # DEFINE EDGES
    # ========================================================================

    # Entry point: conditional routing to planner or generator
    workflow.set_entry_point("generator")  # Start with generator (planner is optional)

    # Optional: If testplan enabled, start with planner
    # workflow.add_conditional_edges(
    #     START,
    #     initial_router,
    #     {
    #         "planner": "planner",
    #         "generator": "generator"
    #     }
    # )

    # Planner → Generator
    workflow.add_edge("planner", "generator")

    # Generator → Critic
    workflow.add_edge("generator", "critic")

    # Critic → Conditional routing
    workflow.add_conditional_edges(
        "critic",
        critique_router,
        {
            "approve": "simulator",   # Good quality → simulate
            "revise": "refiner",      # Minor issues → refine
            "reject": "generator"     # Major issues → regenerate
        }
    )

    # Simulator → Grader
    workflow.add_edge("simulator", "grader")

    # Grader → Conditional routing
    workflow.add_conditional_edges(
        "grader",
        grading_router,
        {
            "complete": END,            # Done (100% coverage)
            "refine": "refiner",        # Continue refining
            "new_approach": "generator", # Stuck, try new approach
            "max_iterations": END       # Hit iteration limit
        }
    )

    # Refiner → Critic (loop back for re-review)
    workflow.add_edge("refiner", "critic")

    logging.info("[Graph] Added edges with conditional routing")

    # ========================================================================
    # COMPILE GRAPH
    # ========================================================================

    try:
        app = workflow.compile()
        logging.info("[Graph] Graph compiled successfully!")
        return app
    except Exception as e:
        logging.error(f"[Graph] Compilation error: {e}")
        raise


def visualize_graph(graph, output_path="verification_graph.png"):
    """
    Visualize the graph structure (requires graphviz).

    Args:
        graph: Compiled LangGraph
        output_path: Output file path for visualization

    Returns:
        None (saves visualization to file)
    """
    try:
        from langgraph.graph import Graph

        # Get mermaid representation
        mermaid = graph.get_graph().draw_mermaid()

        # Save to file
        with open(output_path.replace(".png", ".mmd"), "w") as f:
            f.write(mermaid)

        logging.info(f"[Graph] Mermaid diagram saved to {output_path.replace('.png', '.mmd')}")
        logging.info("[Graph] To visualize: https://mermaid.live/")

    except Exception as e:
        logging.warning(f"[Graph] Could not generate visualization: {e}")
