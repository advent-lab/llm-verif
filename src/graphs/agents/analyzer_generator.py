"""Analyzer-Generator agent for CovAgent v2.

Combines the Design Expert's analysis capability (RTL reading, coverage hole
classification, stimulus recipe design) with the Test Generator's simulation
capability (write, compile, simulate). Each dispatch is stateless — created
fresh per task.

Tool isolation: Simulation tools (write_file, compile_design, run_simulation)
use closures that capture generator-specific paths. Read tools (read_file,
list_directory, get_coverage_status) use the shared module-level instances
already initialized by set_tool_config in the parent graph.
"""

import json
import logging
import subprocess
from copy import copy
from pathlib import Path
from typing import Dict, Any, List, Optional

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from ...config import Config
from ...prompts.loader import load_analyzer_generator_prompt
from ...utils.event_log import emit
from ...utils.conversation_logger import make_generator_logger
from ._result_utils import extract_agent_result


def make_analyzer_generator_tools(
    config: Config,
    iteration: int,
    gen_id: int,
) -> list:
    """Create isolated tool instances for an analyzer-generator agent.

    Returns 6 tools:
    - read_file, list_directory, get_coverage_status (shared, stateless)
    - write_file, compile_design, run_simulation (closure-isolated per generator)

    Args:
        config: Application configuration.
        iteration: Current orchestrator iteration.
        gen_id: Unique generator ID within this iteration.

    Returns:
        List of tool instances.
    """
    # Generator-specific paths
    gen_sim_dir = config.work_dir / "sim_work" / f"gen_{gen_id}"
    gen_sim_dir.mkdir(parents=True, exist_ok=True)

    tb_dir = config.work_dir / "testbenches"
    tb_dir.mkdir(parents=True, exist_ok=True)

    log_dir = config.work_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    coverage_dir = config.work_dir / "coverage"
    coverage_dir.mkdir(parents=True, exist_ok=True)

    # Create generator-specific simulator adapter
    simulator_type = getattr(config, 'simulator_type', 'questasim').lower()
    if simulator_type == 'questasim':
        from ...simulators.questasim_adapter import QuestasimAdapter
        adapter = QuestasimAdapter(config.simulator_path)
    elif simulator_type == 'verilator':
        from ...simulators.verilator_adapter import VerilatorAdapter
        adapter = VerilatorAdapter(config.simulator_path)
    else:
        raise ValueError(f"Unsupported simulator type: {simulator_type}")

    # Initialize QuestaSim work library in generator's sim directory
    if simulator_type == 'questasim':
        work_lib = gen_sim_dir / "work"
        if not work_lib.exists():
            try:
                vlib_cmd = [str(config.simulator_path / "vlib"), str(work_lib)]
                subprocess.run(vlib_cmd, capture_output=True, text=True, timeout=30)
                logging.info(f"Created work library for gen_{gen_id}")
            except Exception as e:
                logging.warning(f"Failed to create work library for gen_{gen_id}: {e}")

    # Mutable retry counter for this generator
    retry_state = {"compile_attempts": 0, "sim_attempts": 0}

    # --- Analysis tools (shared, stateless) ---
    from ...tools.filesystem import read_file, list_directory
    from ...tools.coverage import get_coverage_status

    # --- Tool: write_file ---
    @tool
    def write_file(path: str, content: str) -> Dict[str, Any]:
        """Write content to a file in the work directory.

        Args:
            path: Relative path within the work directory (e.g., "testbenches/tb_iter_3_gen_0.sv")
            content: File content to write.

        Returns:
            Dictionary with success status.
        """
        try:
            file_path = (config.work_dir / path).resolve()
            if not str(file_path).startswith(str(config.work_dir.resolve())):
                return {"success": False, "error": "Path must be within work directory"}
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {"success": True, "path": str(file_path), "size": len(content)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- Tool: compile_design ---
    @tool
    def compile_design(testbench_path: str) -> Dict[str, Any]:
        """Compile the testbench with all design files.

        Args:
            testbench_path: Path to testbench file (relative to work directory).

        Returns:
            Dictionary with success, return_code, stdout, stderr.
        """
        try:
            retry_state["compile_attempts"] += 1
            retry_num = retry_state["compile_attempts"]

            # Hard retry cap
            if retry_num > config.gen_max_retries + 1:
                return {
                    "success": False,
                    "error": f"Compile retry limit reached ({config.gen_max_retries} retries exhausted). "
                             f"Stop retrying compilation and report failure.",
                }

            tb_path = (config.work_dir / testbench_path).resolve()
            if not tb_path.exists():
                return {"success": False, "error": f"Testbench not found: {testbench_path}"}

            design_files = config.design_context_files + config.design_files
            compile_deps_files = getattr(config, 'compile_deps_files', [])

            # Functional coverage: inject stimulus body into the user's template.
            # The patched file is compiled as the testbench; template is NOT
            # prepended to design_files — it is baked into the injected file.
            func_cov_enabled = getattr(config, 'functional_coverage_enabled', False)
            if func_cov_enabled:
                func_cov_tb = getattr(config, 'functional_coverage_testbench_path', None)
                if func_cov_tb:
                    from ...utils.questasim import inject_stimulus_into_template
                    injected_path = tb_path.parent / f"{tb_path.stem}_injected.sv"
                    try:
                        tb_path = inject_stimulus_into_template(func_cov_tb, tb_path, injected_path)
                    except ValueError as e:
                        return {"success": False, "error": str(e)}

            result = adapter.compile(
                testbench_path=tb_path,
                design_files=design_files,
                work_dir=gen_sim_dir,
                timeout=config.sim_timeout,
                compile_deps_files=compile_deps_files,
                functional_coverage=func_cov_enabled,
            )

            if retry_num == 1:
                log_name = f"compile_iter_{iteration}_gen_{gen_id}.log"
            else:
                log_name = f"compile_iter_{iteration}_gen_{gen_id}_retry_{retry_num}.log"

            log_path = log_dir / log_name
            with open(log_path, 'w') as f:
                f.write(f"=== COMPILATION: Iter {iteration}, Gen {gen_id}, Attempt {retry_num} ===\n")
                f.write(f"Testbench: {testbench_path}\n")
                f.write(f"Success: {result.get('success', False)}\n\n")
                f.write(f"STDOUT:\n{result.get('full_stdout', result.get('stdout', ''))}\n\n")
                f.write(f"STDERR:\n{result.get('full_stderr', result.get('stderr', ''))}\n")

            result["log_path"] = str(log_path)
            result.pop("full_stdout", None)
            result.pop("full_stderr", None)

            if result.get("success", False):
                result["stdout"] = f"Compilation successful. Log: {log_name}"
                result.pop("stderr", None)
            else:
                stderr = result.get("stderr", "")
                stdout = result.get("stdout", "")
                error_output = stderr or stdout or "Unknown error"
                result["error_summary"] = f"Compilation failed. Check {log_name}.\n{error_output[:500]}"
                result["stdout"] = adapter.filter_compile_output(result.get("stdout", ""))
                result["stderr"] = adapter.filter_compile_output(result.get("stderr", ""))

            return result

        except Exception as e:
            logging.error(f"Analyzer-Generator {gen_id} compile error: {e}")
            return {"success": False, "error": str(e)}

    # --- Tool: run_simulation ---
    @tool
    def run_simulation(testbench_name: str = "tb_llm", num_runs: int = None) -> Dict[str, Any]:
        """Run simulation with coverage collection.

        Args:
            testbench_name: Name of testbench module (default: "tb_llm").
            num_runs: Number of simulation runs with different seeds (default: from config).

        Returns:
            Dictionary with success, coverage_db_path, stdout.
        """
        try:
            if num_runs is None:
                num_runs = config.sim_runs

            retry_state["sim_attempts"] += 1
            retry_num = retry_state["sim_attempts"]

            # Hard retry cap
            if retry_num > config.gen_max_retries + 1:
                return {
                    "success": False,
                    "error": f"Simulation retry limit reached ({config.gen_max_retries} retries exhausted). "
                             f"Stop retrying simulation and report failure.",
                }

            result = adapter.simulate(
                testbench_name=testbench_name,
                num_runs=num_runs,
                work_dir=gen_sim_dir,
                iteration=iteration,
                timeout=config.sim_timeout,
            )

            # Move coverage DB to shared coverage dir with gen-specific naming
            if result.get("success") and result.get("coverage_db_path"):
                src_db = Path(result["coverage_db_path"])
                if src_db.exists():
                    dest_name = f"cov_iter_{iteration}_gen_{gen_id}.ucdb"
                    dest_db = coverage_dir / dest_name
                    import shutil
                    shutil.copy2(str(src_db), str(dest_db))
                    result["coverage_db_path"] = str(dest_db)
                    logging.info(f"Analyzer-Generator {gen_id} coverage saved to {dest_name}")

            if retry_num == 1:
                log_name = f"sim_iter_{iteration}_gen_{gen_id}.log"
            else:
                log_name = f"sim_iter_{iteration}_gen_{gen_id}_retry_{retry_num}.log"

            log_path = log_dir / log_name
            with open(log_path, 'w') as f:
                f.write(f"=== SIMULATION: Iter {iteration}, Gen {gen_id}, Attempt {retry_num} ===\n")
                f.write(f"Testbench: {testbench_name}\n")
                f.write(f"Num Runs: {num_runs}\n")
                f.write(f"Success: {result.get('success', False)}\n\n")
                f.write(f"STDOUT:\n{result.get('stdout', '')}\n")
                if result.get("stderr"):
                    f.write(f"\nSTDERR:\n{result['stderr']}\n")

            result["log_path"] = str(log_path)

            if result.get("success", False):
                summary = (
                    f"{result.get('num_runs_completed', num_runs)}/{num_runs} "
                    f"runs successful. Log: {log_name}"
                )
                if result.get("warning"):
                    summary += f" Warning: {result['warning']}"
                result["stdout"] = summary
                result.pop("stderr", None)
            else:
                error_msg = result.get("error", "")
                stderr = result.get("stderr", "")
                stdout = result.get("stdout", "")
                error_output = error_msg or stderr or stdout or "Unknown error"
                result["error_summary"] = f"Simulation failed. Check {log_name}.\n{error_output[:500]}"
                result["stdout"] = adapter.filter_sim_output(result.get("stdout", ""))
                result["stderr"] = adapter.filter_sim_output(result.get("stderr", ""))

            return result

        except Exception as e:
            logging.error(f"Analyzer-Generator {gen_id} simulation error: {e}")
            return {"success": False, "error": str(e)}

    return [read_file, list_directory, get_coverage_status,
            write_file, compile_design, run_simulation]


def dispatch_analyzer_generator(
    config: Config,
    task_description: str,
    module_header: str,
    target_module: str,
    coverage_context: str,
    testplan_section: str,
    iteration: int,
    gen_id: int,
    uncovered_bins: Optional[List[dict]] = None,
) -> dict:
    """Create and run a fresh Analyzer-Generator agent.

    The agent reads RTL, analyzes coverage holes, designs stimulus,
    writes a testbench, compiles, and simulates — all independently.

    Args:
        config: Application configuration.
        task_description: High-level verification goal.
        module_header: Verilog module header for the target DUT.
        target_module: Module name being tested ("top" or submodule name).
        coverage_context: Brief coverage summary for context.
        testplan_section: Relevant portion of the testplan.
        iteration: Current orchestrator iteration.
        gen_id: Unique generator ID.

    Returns:
        Dict with: success, summary, coverage_db_path, testbench_path, gen_id.
    """
    logging.info(f"Dispatching analyzer-generator {gen_id} (iter {iteration}, "
                 f"target={target_module})")

    emit("analyzer_generator_dispatch", {
        "gen_id": gen_id,
        "iteration": iteration,
        "target_module": target_module,
        "task_preview": task_description[:200],
    })

    try:
        # Create agent-specific tools
        agent_tools = make_analyzer_generator_tools(config, iteration, gen_id)

        # Build LLM
        llm_kwargs = dict(
            model=config.analyzer_generator_model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            api_key=config.openai_api_key,
        )
        if config.reasoning_effort != "disabled":
            llm_kwargs["reasoning_effort"] = config.reasoning_effort

        # Load system prompt
        system_prompt = load_analyzer_generator_prompt(
            design_name=config.design_name,
            design_dir=config.design_dir,
            spec_path=config.spec_path,
            design_files=config.design_files,
            design_context_files=config.design_context_files,
        )

        # Create fresh agent
        agent = create_agent(
            model=ChatOpenAI(**llm_kwargs),
            tools=agent_tools,
            system_prompt=system_prompt,
            name=f"analyzer_generator_{gen_id}",
        )

        # Build testbench path for this agent
        tb_filename = f"tb_iter_{iteration}_gen_{gen_id}.sv"
        tb_path = f"testbenches/{tb_filename}"

        # Build task message (mode-aware)
        func_cov_enabled = getattr(config, 'functional_coverage_enabled', False)
        func_cov_tb = getattr(config, 'functional_coverage_testbench_path', None)

        task_parts = [
            f"## Task\n{task_description}",
            f"\n## Target Module: {target_module}",
            f"\n## Module Header\n```verilog\n{module_header}\n```",
        ]
        if coverage_context:
            task_parts.append(f"\n## Current Coverage Context\n{coverage_context}")
        if testplan_section:
            task_parts.append(f"\n## Testplan Section\n{testplan_section}")

        if func_cov_enabled and func_cov_tb:
            if uncovered_bins:
                bins_summary = "\n".join(
                    f"  - {b.get('covergroup','?')}.{b.get('coverpoint','?')}: `{b.get('bin_name','?')}`"
                    for b in uncovered_bins[:20]
                )
            else:
                bins_summary = "  (none listed — sweep all coverpoints)"
            task_parts.append(
                f"\n## Functional Coverage Mode — STIMULUS BODY ONLY\n"
                f"Testbench template: `{func_cov_tb}` — read it to understand covergroups, bins, and the sample event.\n"
                f"The framework injects your stimulus into the template automatically.\n\n"
                f"**Write ONLY the body lines** of the initial block to `{tb_path}` — "
                f"do NOT include `initial begin`, `$finish;`, `end`, or any module wrapper. "
                f"The framework adds these automatically.\n\n"
                f"Uncovered bins to target:\n{bins_summary}"
            )
            task_parts.append(
                f"\n## Instructions\n"
                f"1. Read the testbench template at `{func_cov_tb}` to understand covergroup structure and port names\n"
                f"2. Read RTL file(s) for `{target_module}` to understand signal semantics\n"
                f"3. Analyze each uncovered bin: what signal value / sequence is needed?\n"
                f"4. Write ONLY the stimulus body lines to `{tb_path}` "
                f"(no `initial begin`, no `$finish;`, no `end`, no module)\n"
                f"5. Compile with `compile_design(\"{tb_path}\")`\n"
                f"6. Simulate with `run_simulation(testbench_name=\"tb_llm\")`\n"
                f"7. Fix and retry on failures (max {config.gen_max_retries} retries)\n"
                f"8. On success, report the coverage database path"
            )
        else:
            task_parts.append(
                f"\n## Instructions\n"
                f"1. Read the relevant RTL source file(s) for `{target_module}` to understand the implementation\n"
                f"2. Check coverage with `get_coverage_status(\"detailed\")` to identify uncovered lines\n"
                f"3. Analyze: trace backward from uncovered lines to determine activation paths\n"
                f"4. Design a stimulus recipe targeting the uncovered code paths\n"
                f"5. Write your testbench to `{tb_path}`\n"
                f"6. The testbench module MUST be named `tb_llm`\n"
                f"7. Instantiate `{target_module}` as the DUT\n"
                f"8. Compile with `compile_design`, then simulate with `run_simulation`\n"
                f"9. If compile or simulation fails, fix and retry (max {config.gen_max_retries} total failures)\n"
                f"10. On success, summarize your analysis, the stimulus strategy, any M1-M3 holes found, "
                f"and report the coverage database path"
            )
        task_message = "\n".join(task_parts)

        # Recursion limit: generous to allow analysis + retries
        # Analysis adds ~6-10 tool calls (read RTL, coverage, list_dir)
        # then generation adds ~6 per retry
        recursion_limit = max(80, config.gen_max_retries * 15 + 30)

        conv_logger = make_generator_logger(iteration, gen_id)
        conv_logger.agent_name = f"analyzer_generator_iter_{iteration}_gen_{gen_id}"
        conv_logger.log_path = conv_logger.log_path.parent / f"analyzer_generator_iter_{iteration}_gen_{gen_id}.log"

        result = agent.invoke(
            {"messages": [HumanMessage(content=task_message)]},
            config={"recursion_limit": recursion_limit, "callbacks": [conv_logger]},
        )

        # Extract results
        return extract_agent_result(
            result, gen_id, iteration, target_module, tb_path,
            agent_type="analyzer_generator",
        )

    except Exception as e:
        error_msg = f"Analyzer-Generator {gen_id} dispatch error: {str(e)}"
        logging.error(error_msg)
        emit("analyzer_generator_error", {
            "gen_id": gen_id,
            "iteration": iteration,
            "error": str(e),
        })
        return {
            "success": False,
            "summary": error_msg,
            "coverage_db_path": None,
            "testbench_path": None,
            "gen_id": gen_id,
            "target_module": target_module,
        }
