"""Orchestrator tools for CovAgent v2.1 (Analyzer-Generator + CRT architecture).

Defines the v2.1 Orchestrator's tool set: dispatch_analyzer_generator,
dispatch_crt_agent, get_coverage_status, write_file, read_file. Tools are
created as closures that capture gen_context and config.

NOTE: This is the v2.1 counterpart to orchestrator.py (v2). The key difference
is that v2.1 has no Design Expert — instead, Analyzer-Generator agents read
RTL and analyze coverage holes independently per dispatch.
"""

import json
import logging

from langchain.tools import tool

from ...config import Config
from ...utils.event_log import emit
from .analyzer_generator import dispatch_analyzer_generator as _dispatch_ag
from .crt_agent import dispatch_crt_agent as _dispatch_crt


def make_ag_crt_orchestrator_tools(config: Config, gen_context: dict) -> list:
    """Create the Orchestrator's tool set for the v2.1 AG+CRT architecture.

    Tools are closures that capture the gen_context dict (mutable) and config.
    The gen_context dict is updated by the parent graph's update_state_node
    to keep iteration and gen_id current.

    Args:
        config: Application configuration.
        gen_context: Mutable dict with keys:
            - "iteration": current iteration number
            - "next_gen_id": next generator ID to assign

    Returns:
        List of tools for the v2.1 Orchestrator agent.
    """

    @tool
    def dispatch_analyzer_generator(
        task_description: str,
        module_header: str,
        target_module: str = "top",
        coverage_context: str = "",
        testplan_section: str = "",
    ) -> str:
        """Dispatch an Analyzer-Generator to analyze coverage holes and generate targeted stimulus.

        The agent has full RTL read access and will independently:
        1. Read relevant RTL source files for the target module
        2. Check coverage status to identify specific uncovered lines
        3. Trace backward from uncovered lines to find the activation path
        4. Design a targeted stimulus recipe based on its analysis
        5. Write a testbench, compile, and simulate

        Use this for targeted coverage closure — give the agent a high-level goal
        and let it determine the detailed strategy. Describe WHAT to target, not HOW.

        You can dispatch multiple agents in a single response — they execute in parallel.

        Args:
            task_description: High-level verification goal. Name the feature or
                coverage region to target. Do NOT prescribe exact RTL paths —
                the agent reads the RTL itself and determines the approach.
                Example: "Target the CRC computation paths in can_bsp" or
                "Cover FIFO discard and overflow edge cases in the data path".
            module_header: Verilog module header for the target DUT.
                Use the top-level header from your system prompt for top-level
                testing, or extract a submodule header via read_file on the RTL.
            target_module: Module name being tested. Use "top" for the top-level
                module, or the actual module name (e.g., "can_bsp") for unit-level.
            coverage_context: Brief current coverage summary for context (optional).
                A short note on which modules have holes and rough percentages helps
                the agent prioritize within its assigned scope.
            testplan_section: Relevant portion of your testplan for this task.

        Returns:
            JSON with: success (bool), summary (str), coverage_db_path (str),
            testbench_path (str), gen_id (int), target_module (str).
        """
        iteration = gen_context["iteration"]
        gen_id = gen_context["next_gen_id"]
        gen_context["next_gen_id"] += 1

        result = _dispatch_ag(
            config=config,
            task_description=task_description,
            module_header=module_header,
            target_module=target_module,
            coverage_context=coverage_context,
            testplan_section=testplan_section,
            iteration=iteration,
            gen_id=gen_id,
        )

        emit("orchestrator_ag_dispatch", {
            "gen_id": gen_id,
            "iteration": iteration,
            "target_module": target_module,
            "success": result.get("success", False),
        })

        return json.dumps(result)

    @tool
    def dispatch_crt_agent(
        task_description: str,
        module_header: str,
        target_module: str = "top",
        design_context: str = "",
    ) -> str:
        """Dispatch a CRT (Constrained Random Test) agent for broad randomized stimulus.

        The CRT agent generates broad, varied randomized stimulus without performing
        detailed coverage analysis. It is most effective in early verification phases
        when many lines remain uncovered and broad stimulus can quickly sweep them.

        The CRT agent has only 3 tools: write_file, compile_design, run_simulation.
        It CANNOT read files or explore the design directory. All design context it
        needs must be provided in the design_context parameter.

        You can dispatch multiple CRT agents in parallel — each targeting a different
        subsystem, operating mode, or input scenario.

        Args:
            task_description: What randomized patterns to generate. Be specific
                about which subsystem, operating mode, or input range to exercise.
                Example: "Broad randomized register access across all addresses with
                random inter-transaction delays" or "Random reset and mode transitions
                covering all combinations of mode control bits".
            module_header: Verilog module header for the target DUT.
            target_module: Module name being tested. Use "top" for the top-level
                module, or the actual module name for unit-level.
            design_context: Key design details the agent needs to write valid stimulus.
                The agent cannot read files, so include everything it needs here:
                port semantics, register addresses, protocol sequences, clock domains,
                reset polarity, bus widths, handshake protocols. The more context you
                provide, the better the agent's stimulus will be.

        Returns:
            JSON with: success (bool), summary (str), coverage_db_path (str),
            testbench_path (str), gen_id (int), target_module (str).
        """
        iteration = gen_context["iteration"]
        gen_id = gen_context["next_gen_id"]
        gen_context["next_gen_id"] += 1

        result = _dispatch_crt(
            config=config,
            task_description=task_description,
            module_header=module_header,
            target_module=target_module,
            design_context=design_context,
            iteration=iteration,
            gen_id=gen_id,
        )

        emit("orchestrator_crt_dispatch", {
            "gen_id": gen_id,
            "iteration": iteration,
            "target_module": target_module,
            "success": result.get("success", False),
        })

        return json.dumps(result)

    from ...tools.filesystem import read_file, write_file
    from ...tools.coverage import get_coverage_status

    return [
        dispatch_analyzer_generator,
        dispatch_crt_agent,
        get_coverage_status,
        write_file,
        read_file,
    ]
