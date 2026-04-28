"""Orchestrator tools for CovAgent v3 (Orchestrator + Iterative Test Generator).

The v3 orchestrator's tool set is intentionally small:
    - read_file, write_file, list_directory  (shared filesystem tools)
    - get_coverage_status                    (shared, run-level cache)
    - dispatch_test_generator                (NEW — the headline tool)

The single dispatch tool takes a `mode` parameter ("crt" | "directed") so the
orchestrator can vary stimulus strategy without needing two separate tools.
The actual sub-agent is implemented in test_generator_v3.py.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Literal

from langchain.tools import tool

from ...config import Config
from ...utils.event_log import emit
from .test_generator_v3 import dispatch_test_generator_v3


def make_orc_gen_orchestrator_tools(config: Config, gen_context: dict) -> list:
    """Build the v3 orchestrator's tool set.

    Args:
        config: Application configuration.
        gen_context: Mutable dict carrying {"iteration": int, "next_gen_id": int}.
            update_state_node mutates this between iterations so the right
            iteration / gen_id labels propagate into log paths and coverage DBs.

    Returns:
        List of LangChain tools the orchestrator agent will be bound to.
    """

    @tool
    def dispatch_test_generator(
        mode: Literal["crt", "directed"],
        task_description: str,
        testplan_path: str,
        target_module: str = "top",
        module_header: str = "",
        design_files_access: List[str] = [],
        coverage_context: str = "",
    ) -> str:
        """Dispatch a Test Generator sub-agent that iterates write→compile→sim
        across multiple successful coverage rounds and returns a Test Summary.

        Each dispatch is fresh — no memory across dispatches. You may emit
        multiple `dispatch_test_generator` tool calls in one response; they
        run in parallel.

        Args:
            mode: "crt" for broad randomized stimulus, "directed" for targeted
                hole closure.
            task_description: Short imperative description of what to stimulate
                and why. Strategy details belong in the testplan file, not here.
            testplan_path: Path to the testplan file you already wrote with
                write_file (relative to work directory, e.g.
                "crt_testplan.md" or "directed_testplan_chacha.md"). The
                framework reads the file and injects its content for the
                sub-agent — do NOT inline the full text here.
            target_module: "top" for top-level testing, or a submodule name for
                unit-level. Defaults to "top".
            module_header: Verilog module header for the target. Use the
                top-level header from your system prompt for "top"; for
                submodules, copy the header from the relevant RTL file.
            design_files_access: WHITELIST of absolute file paths the sub-agent
                may `read_file`. Anything outside this list is refused. Pass an
                empty list to forbid all reads (the agent will work purely from
                this task message). Pick the minimum useful set.
            coverage_context: Short prose summary of the most relevant
                uncovered regions (1–3 sentences). Skip on the very first
                dispatch when coverage is 0%.

        Returns:
            JSON string with: success, mode, gen_id, target_module,
            testbench_path, coverage_db_path, iterations_completed, summary,
            final_iteration_coverage.
        """
        iteration = gen_context["iteration"]
        gen_id = gen_context["next_gen_id"]
        gen_context["next_gen_id"] += 1

        normalized_mode = (mode or "directed").lower().strip()
        if normalized_mode not in ("crt", "directed"):
            normalized_mode = "directed"

        # Read testplan content from the file the orchestrator already wrote.
        try:
            tp_file = (config.work_dir / testplan_path).resolve()
            testplan_content = tp_file.read_text(encoding="utf-8")
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Could not read testplan file '{testplan_path}': {e}",
                "mode": normalized_mode,
                "gen_id": gen_id,
            })

        result = dispatch_test_generator_v3(
            config=config,
            mode=normalized_mode,
            task_description=task_description,
            testplan=testplan_content,
            target_module=target_module,
            module_header=module_header,
            design_files_access=list(design_files_access or []),
            coverage_context=coverage_context,
            iteration=iteration,
            gen_id=gen_id,
        )

        emit("orchestrator_v3_dispatch", {
            "gen_id": gen_id,
            "iteration": iteration,
            "mode": normalized_mode,
            "target_module": target_module,
            "success": result.get("success", False),
            "iterations_completed": result.get("iterations_completed", 0),
        })

        return json.dumps(result)

    from ...tools.filesystem import read_file, write_file, list_directory
    from ...tools.coverage import get_coverage_status

    return [
        dispatch_test_generator,
        get_coverage_status,
        read_file,
        write_file,
        list_directory,
    ]
