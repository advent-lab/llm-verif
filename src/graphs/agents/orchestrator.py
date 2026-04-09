"""Orchestrator agent tools for CovAgent v2.

Defines the Orchestrator's tool set: query_design_expert, dispatch_test_generator,
get_coverage_status, write_file, read_file. Tools are created as closures that
capture the expert graph, generator context, and config.
"""

import json
import logging
from typing import Dict, Any, List

from langchain.tools import tool
from langgraph.graph.state import CompiledStateGraph

from ...config import Config
from ...utils.event_log import emit
from .design_expert import invoke_expert
from .test_generator import dispatch_generator


def make_orchestrator_tools(
    config: Config,
    expert_graph: CompiledStateGraph,
    expert_thread_id: str,
    gen_context: dict,
) -> list:
    """Create the Orchestrator's tool set.

    Tools are closures that capture the expert graph, generator context,
    and config. The gen_context dict is mutable and updated by the parent
    graph's update_state_node to keep iteration and gen_id current.

    Args:
        config: Application configuration.
        expert_graph: Compiled Design Expert agent graph.
        expert_thread_id: Fixed thread ID for expert persistence.
        gen_context: Mutable dict with keys:
            - "iteration": current iteration number
            - "next_gen_id": next generator ID to assign

    Returns:
        List of tools for the Orchestrator agent.
    """

    @tool
    def query_design_expert(query: str) -> str:
        """Query the Design Expert for design analysis, coverage hole
        classification, stimulus recipes, or module header extraction.

        The expert maintains persistent memory across queries within this run.
        It has access to read_file, list_directory, and get_coverage_status tools.
        It remembers everything it has read and analyzed.

        Args:
            query: Natural language question or request for the design expert.
                Be specific about what you need — the expert responds thoroughly.

        Returns:
            Expert's natural language response with analysis, classifications,
            stimulus recipes, or other requested information.
        """
        response = invoke_expert(expert_graph, expert_thread_id, query, config)

        emit("orchestrator_expert_query", {
            "query_preview": query[:200],
            "response_length": len(response),
        })

        return response

    @tool
    def dispatch_test_generator(
        task_description: str,
        module_header: str,
        target_module: str = "top",
        design_context: str = "",
        testplan_section: str = "",
    ) -> str:
        """Dispatch a Test Generator to create and verify a testbench.

        The generator is a fresh agent that writes a testbench, compiles,
        simulates, and retries errors internally. It returns a summary
        and the coverage database path on success.

        You can dispatch multiple generators in a single response — they
        execute in parallel via the framework's ToolNode.

        Args:
            task_description: What stimulus to generate and why. Be specific
                about signals, protocols, sequences, and expected behavior.
                Include any stimulus recipes from the Design Expert.
            module_header: Verilog module header for the target DUT. For top-level,
                use the module header from your system prompt. For unit-level,
                get the header from the Design Expert via query_design_expert.
            target_module: Module name being tested. Use "top" for the top-level
                module, or the actual module name (e.g., "can_bsp") for unit-level.
            design_context: Relevant analysis from the Design Expert — protocol
                details, signal semantics, timing requirements.
            testplan_section: Relevant portion of your testplan for this task.

        Returns:
            JSON string with: success (bool), summary (str), coverage_db_path (str),
            testbench_path (str), gen_id (int), target_module (str).
        """
        iteration = gen_context["iteration"]
        gen_id = gen_context["next_gen_id"]
        gen_context["next_gen_id"] += 1

        result = dispatch_generator(
            config=config,
            task_description=task_description,
            module_header=module_header,
            target_module=target_module,
            testplan_section=testplan_section,
            design_context=design_context,
            iteration=iteration,
            gen_id=gen_id,
        )

        emit("orchestrator_gen_dispatch", {
            "gen_id": gen_id,
            "iteration": iteration,
            "target_module": target_module,
            "success": result.get("success", False),
        })

        return json.dumps(result)

    # Import filesystem tools
    from ...tools.filesystem import read_file, write_file

    # Import shared coverage tool
    from ...tools.coverage import get_coverage_status

    return [
        query_design_expert,
        dispatch_test_generator,
        get_coverage_status,
        write_file,
        read_file,
    ]
