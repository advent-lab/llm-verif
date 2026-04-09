"""CRT (Constrained Random Test) agent for CovAgent v2.1.

Generates broad randomized stimulus for quick early-phase coverage sweep.
Each dispatch is stateless — created fresh per task. Does NOT perform
detailed coverage analysis or read RTL; follows orchestrator instructions
and design context injected at dispatch time.

Tool isolation: Same closure pattern as the Analyzer-Generator for
simulation tools (write_file, compile_design, run_simulation).

The CRT agent has only 3 tools — write_file, compile_design, run_simulation.
All design context (port semantics, register maps, protocol info) is injected
into the task message by the orchestrator. No read_file or list_directory.
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
from ...prompts.loader import load_crt_prompt
from ...utils.event_log import emit
from ...utils.conversation_logger import make_generator_logger
from ._result_utils import extract_agent_result


def make_crt_tools(
    config: Config,
    iteration: int,
    gen_id: int,
) -> list:
    """Create isolated tool instances for a CRT agent.

    Returns 3 tools (no read_file or list_directory — CRT agents receive
    all design context in the task message and should not explore):
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

            result = adapter.compile(
                testbench_path=tb_path,
                design_files=design_files,
                work_dir=gen_sim_dir,
                timeout=config.sim_timeout,
                compile_deps_files=compile_deps_files,
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
            logging.error(f"CRT {gen_id} compile error: {e}")
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
                    logging.info(f"CRT {gen_id} coverage saved to {dest_name}")

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
            logging.error(f"CRT {gen_id} simulation error: {e}")
            return {"success": False, "error": str(e)}

    return [write_file, compile_design, run_simulation]


def dispatch_crt_agent(
    config: Config,
    task_description: str,
    module_header: str,
    target_module: str,
    design_context: str,
    iteration: int,
    gen_id: int,
) -> dict:
    """Create and run a fresh CRT agent.

    The agent generates broad randomized stimulus based on the task
    description and design context provided by the orchestrator.

    Args:
        config: Application configuration.
        task_description: What randomized stimulus patterns to generate.
        module_header: Verilog module header for the target DUT.
        target_module: Module name being tested ("top" or submodule name).
        design_context: Design details the agent needs — port semantics, register
            addresses, protocol sequences, clock domains. The agent cannot read
            files, so all needed context must be included here.
        iteration: Current orchestrator iteration.
        gen_id: Unique generator ID.

    Returns:
        Dict with: success, summary, coverage_db_path, testbench_path, gen_id.
    """
    logging.info(f"Dispatching CRT agent {gen_id} (iter {iteration}, "
                 f"target={target_module})")

    emit("crt_dispatch", {
        "gen_id": gen_id,
        "iteration": iteration,
        "target_module": target_module,
        "task_preview": task_description[:200],
    })

    try:
        # Create agent-specific tools
        agent_tools = make_crt_tools(config, iteration, gen_id)

        # Build LLM
        llm_kwargs = dict(
            model=config.crt_model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            api_key=config.openai_api_key,
        )
        if config.reasoning_effort != "disabled":
            llm_kwargs["reasoning_effort"] = config.reasoning_effort

        # Load system prompt
        system_prompt = load_crt_prompt(design_name=config.design_name)

        # Create fresh agent
        agent = create_agent(
            model=ChatOpenAI(**llm_kwargs),
            tools=agent_tools,
            system_prompt=system_prompt,
            name=f"crt_{gen_id}",
        )

        # Build testbench path for this agent
        tb_filename = f"tb_iter_{iteration}_gen_{gen_id}.sv"
        tb_path = f"testbenches/{tb_filename}"

        # Build task message — all context the agent needs is here
        task_parts = [
            f"## Task\n{task_description}",
            f"\n## Target Module: {target_module}",
            f"\n## Module Header\n```verilog\n{module_header}\n```",
        ]
        if design_context:
            task_parts.append(f"\n## Design Context\n{design_context}")
        task_parts.append(
            f"\n## Instructions\n"
            f"- Write a randomized testbench to `{tb_path}` on your FIRST turn\n"
            f"- The testbench module MUST be named `tb_llm`\n"
            f"- Instantiate `{target_module}` as the DUT\n"
            f"- Use broad randomized stimulus: $urandom, varied timing, multiple scenarios\n"
            f"- Compile with `compile_design(\"{tb_path}\")`, then simulate with `run_simulation()`\n"
            f"- If compile or simulation fails, read the error, fix the testbench, and retry (max {config.gen_max_retries} retries)\n"
            f"- On success, report the coverage database path from the simulation result"
        )
        task_message = "\n".join(task_parts)

        # Recursion limit: write + (compile+fix)*retries + sim + margin
        # With gen_max_retries=3: (3+1)*10+20 = 60 → 30 turns
        recursion_limit = max(60, (config.gen_max_retries + 1) * 10 + 20)

        conv_logger = make_generator_logger(iteration, gen_id)
        conv_logger.agent_name = f"crt_iter_{iteration}_gen_{gen_id}"
        conv_logger.log_path = conv_logger.log_path.parent / f"crt_iter_{iteration}_gen_{gen_id}.log"

        result = agent.invoke(
            {"messages": [HumanMessage(content=task_message)]},
            config={"recursion_limit": recursion_limit, "callbacks": [conv_logger]},
        )

        # Extract results
        return extract_agent_result(
            result, gen_id, iteration, target_module, tb_path,
            agent_type="crt",
        )

    except Exception as e:
        error_msg = f"CRT {gen_id} dispatch error: {str(e)}"
        logging.error(error_msg)
        emit("crt_error", {
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
