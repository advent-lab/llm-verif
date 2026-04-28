"""Iterative Test Generator agent for CovAgent v3.

Differences vs. v2 / v2.1 generators:
    - Runs MULTIPLE successful coverage rounds per dispatch (not one-shot).
    - Has a whitelisted read_file (only paths the orchestrator opted in).
    - Uses an in-tool counter (`successful_rounds`) to enforce a hard cap on
      rounds, in addition to the existing compile/sim retry caps.
    - Maintains a *dispatch-level* cumulative UCDB across rounds, returned to
      the orchestrator for the run-level merge.

The dispatch is otherwise the same shape as today's analyzer_generator / crt_agent:
    - create_agent() + ChatOpenAI with the configured generator model
    - Closure-isolated tools per gen_id (own work_dir, own simulator adapter)
    - Final structured result extracted from message history
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain.tools import tool
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

from ...config import Config
from ...prompts.loader import load_orc_gen_test_generator_prompt
from ...utils.event_log import emit
from ...utils.conversation_logger import make_generator_logger


# ----------------------------------------------------------------------------
# Tool factory
# ----------------------------------------------------------------------------

def make_generator_v3_tools(
    config: Config,
    iteration: int,
    gen_id: int,
    mode: str,
    allowed_files: List[str],
) -> tuple[list, dict]:
    """Build closure-isolated tools for one v3 generator dispatch.

    Returns:
        (tools, retry_state) — retry_state lets dispatch_test_generator_v3
        read out per-dispatch counters after agent.invoke() returns.
    """
    work_dir = config.work_dir
    gen_sim_dir = work_dir / "sim_work" / f"gen_{gen_id}"
    gen_sim_dir.mkdir(parents=True, exist_ok=True)

    tb_dir = work_dir / "testbenches"
    tb_dir.mkdir(parents=True, exist_ok=True)

    log_dir = work_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Per-generator coverage artifacts live under sim_work/gen_{id}/.
    # The run-level cumulative DB at work/coverage/cumulative.ucdb is
    # managed solely by orc_gen.update_state_node — generators never touch it.
    gen_cov_dir = gen_sim_dir
    gen_cov_dir.mkdir(parents=True, exist_ok=True)

    dispatch_cumulative_db = (
        gen_cov_dir / f"dispatch_iter_{iteration}_cumulative.ucdb"
    )

    # Seed the dispatch cumulative with a snapshot of the run-level cumulative
    # so this generator's parse_coverage feedback reflects what is still
    # uncovered globally minus whatever this dispatch closes. Parallel dispatches
    # start from the same snapshot; the run-level merge happens in
    # update_state_node after all dispatches finish.
    global_cumulative = work_dir / "coverage" / "cumulative.ucdb"
    if global_cumulative.exists() and not dispatch_cumulative_db.exists():
        try:
            shutil.copy2(str(global_cumulative), str(dispatch_cumulative_db))
            logging.info(
                f"v3 gen_{gen_id}: seeded dispatch cumulative from "
                f"run-level cumulative ({global_cumulative})"
            )
        except Exception as e:
            logging.warning(
                f"v3 gen_{gen_id}: could not seed dispatch cumulative: {e}"
            )

    # Resolve whitelist to absolute paths once.
    whitelist = set()
    for p in (allowed_files or []):
        try:
            whitelist.add(str(Path(p).resolve()))
        except Exception:
            whitelist.add(str(p))

    simulator_type = getattr(config, 'simulator_type', 'questasim').lower()
    if simulator_type == 'questasim':
        from ...simulators.questasim_adapter import QuestasimAdapter
        adapter = QuestasimAdapter(config.simulator_path)
    elif simulator_type == 'verilator':
        from ...simulators.verilator_adapter import VerilatorAdapter
        adapter = VerilatorAdapter(config.simulator_path)
    else:
        raise ValueError(f"Unsupported simulator type: {simulator_type}")

    if simulator_type == 'questasim':
        work_lib = gen_sim_dir / "work"
        if not work_lib.exists():
            try:
                vlib_cmd = [str(config.simulator_path / "vlib"), str(work_lib)]
                subprocess.run(vlib_cmd, capture_output=True, text=True, timeout=30)
                logging.info(f"v3 gen_{gen_id}: created work library")
            except Exception as e:
                logging.warning(f"v3 gen_{gen_id}: vlib failed: {e}")

    retry_state = {
        "compile_attempts": 0,
        "sim_attempts": 0,
        "successful_rounds": 0,
        "last_round_coverage": 0.0,
        "rounds_terminated_reason": None,
        "dispatch_cumulative_db": str(dispatch_cumulative_db),
    }

    func_cov_enabled = getattr(config, 'functional_coverage_enabled', False)
    func_cov_tb = getattr(config, 'functional_coverage_testbench_path', None)

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @tool
    def read_file(path: str) -> Dict[str, Any]:
        """Read a file. Restricted to the whitelist for this dispatch.

        Args:
            path: File path. Must resolve to one of the orchestrator-supplied
                allowed paths, otherwise the call is refused.

        Returns:
            {"success": bool, "content": str, "error": str}
        """
        try:
            resolved = str(Path(path).resolve())
        except Exception as e:
            return {"success": False, "error": f"Invalid path {path!r}: {e}"}

        # Always allow files inside the work_dir — generator artifacts.
        try:
            inside_work = str(Path(resolved)).startswith(str(work_dir.resolve()))
        except Exception:
            inside_work = False

        if not inside_work and resolved not in whitelist:
            allowed_preview = "\n".join(f"   - {p}" for p in sorted(whitelist)[:10])
            return {
                "success": False,
                "error": (
                    f"read_file refused: {path} is not in this dispatch's "
                    f"whitelist. Allowed paths:\n{allowed_preview}"
                ),
            }
        try:
            content = Path(resolved).read_text(encoding='utf-8', errors='replace')
            return {"success": True, "content": content}
        except FileNotFoundError:
            return {"success": False, "error": f"File not found: {path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @tool
    def write_file(path: str, content: str) -> Dict[str, Any]:
        """Write a file inside the work directory.

        Args:
            path: Relative path (e.g., "testbenches/tb_iter_1_gen_0_round_2.sv").
            content: File content.
        """
        try:
            file_path = (work_dir / path).resolve()
            if not str(file_path).startswith(str(work_dir.resolve())):
                return {"success": False, "error": "Path must be within work directory"}
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {"success": True, "path": str(file_path), "size": len(content)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @tool
    def compile_design(testbench_path: str) -> Dict[str, Any]:
        """Compile testbench + design files for this dispatch.

        Args:
            testbench_path: Path to testbench (relative to work directory).
        """
        try:
            retry_state["compile_attempts"] += 1
            attempt = retry_state["compile_attempts"]

            if attempt > config.gen_max_retries + 1:
                retry_state["rounds_terminated_reason"] = "compile_retry_exhausted"
                return {
                    "success": False,
                    "error": (
                        f"Compile retry limit reached "
                        f"({config.gen_max_retries} retries exhausted). "
                        f"Stop calling tools and emit your final ## Test Summary."
                    ),
                }

            tb_path = (work_dir / testbench_path).resolve()
            if not tb_path.exists():
                return {"success": False, "error": f"Testbench not found: {testbench_path}"}

            design_files = config.design_context_files + config.design_files
            compile_deps_files = getattr(config, 'compile_deps_files', [])

            if func_cov_enabled and func_cov_tb:
                from ...utils.questasim import inject_stimulus_into_template
                injected_path = tb_path.parent / f"{tb_path.stem}_injected.sv"
                try:
                    tb_path = inject_stimulus_into_template(
                        func_cov_tb, tb_path, injected_path
                    )
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

            log_name = (
                f"compile_iter_{iteration}_gen_{gen_id}_attempt_{attempt}.log"
            )
            log_path = log_dir / log_name
            with open(log_path, 'w') as f:
                f.write(
                    f"=== COMPILE: iter {iteration}, gen {gen_id}, "
                    f"attempt {attempt} ===\n"
                    f"Testbench: {testbench_path}\n"
                    f"Success: {result.get('success', False)}\n\n"
                )
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
                result["error_summary"] = (
                    f"Compilation failed. Check {log_name}.\n{error_output[:500]}"
                )
                result["stdout"] = adapter.filter_compile_output(result.get("stdout", ""))
                result["stderr"] = adapter.filter_compile_output(result.get("stderr", ""))

            return result
        except Exception as e:
            logging.error(f"v3 gen_{gen_id} compile error: {e}")
            return {"success": False, "error": str(e)}

    @tool
    def run_simulation(
        testbench_name: str = "tb_llm",
        num_runs: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run simulation with coverage; merges into the dispatch cumulative DB.

        Args:
            testbench_name: Testbench module name (default "tb_llm").
            num_runs: Number of seeded runs (default: config.sim_runs).
        """
        try:
            if num_runs is None:
                num_runs = config.sim_runs

            retry_state["sim_attempts"] += 1
            attempt = retry_state["sim_attempts"]

            if attempt > config.gen_max_retries + 1:
                retry_state["rounds_terminated_reason"] = "sim_retry_exhausted"
                return {
                    "success": False,
                    "error": (
                        f"Simulation retry limit reached "
                        f"({config.gen_max_retries} retries exhausted). "
                        f"Stop calling tools and emit your final ## Test Summary."
                    ),
                }

            result = adapter.simulate(
                testbench_name=testbench_name,
                num_runs=num_runs,
                work_dir=gen_sim_dir,
                iteration=iteration,
                timeout=config.sim_timeout,
            )

            # Persist per-round DB, merge into dispatch cumulative
            round_db_path = None
            if result.get("success") and result.get("coverage_db_path"):
                src_db = Path(result["coverage_db_path"])
                if src_db.exists():
                    round_idx = retry_state["successful_rounds"] + 1
                    dest_name = (
                        f"cov_iter_{iteration}_round_{round_idx}.ucdb"
                    )
                    round_db_path = gen_cov_dir / dest_name
                    shutil.copy2(str(src_db), str(round_db_path))
                    result["coverage_db_path"] = str(round_db_path)

                    try:
                        adapter.merge_cumulative_coverage(
                            round_db_path, dispatch_cumulative_db
                        )
                        result["dispatch_cumulative_db_path"] = str(dispatch_cumulative_db)
                    except Exception as e:
                        logging.error(
                            f"v3 gen_{gen_id} cumulative merge failed: {e}"
                        )

                    retry_state["successful_rounds"] += 1
                    retry_state["last_round_db"] = str(round_db_path)

            log_name = (
                f"sim_iter_{iteration}_gen_{gen_id}_attempt_{attempt}.log"
            )
            log_path = log_dir / log_name
            with open(log_path, 'w') as f:
                f.write(
                    f"=== SIM: iter {iteration}, gen {gen_id}, "
                    f"attempt {attempt} ===\n"
                    f"Testbench: {testbench_name}\n"
                    f"Num Runs: {num_runs}\n"
                    f"Success: {result.get('success', False)}\n"
                    f"Successful rounds so far: {retry_state['successful_rounds']}\n\n"
                )
                f.write(f"STDOUT:\n{result.get('stdout', '')}\n")
                if result.get("stderr"):
                    f.write(f"\nSTDERR:\n{result['stderr']}\n")

            result["log_path"] = str(log_path)

            if result.get("success", False):
                summary = (
                    f"{result.get('num_runs_completed', num_runs)}/{num_runs} "
                    f"runs successful. Log: {log_name}. "
                    f"Round {retry_state['successful_rounds']}/"
                    f"{config.gen_max_iterations} for this dispatch."
                )
                if result.get("warning"):
                    summary += f" Warning: {result['warning']}"
                result["stdout"] = summary
                result.pop("stderr", None)
                result["successful_rounds"] = retry_state["successful_rounds"]
                result["max_rounds"] = config.gen_max_iterations

                if retry_state["successful_rounds"] >= config.gen_max_iterations:
                    retry_state["rounds_terminated_reason"] = "max_rounds"
                    result["framework_notice"] = (
                        f"You have completed your final coverage round "
                        f"({retry_state['successful_rounds']}/"
                        f"{config.gen_max_iterations}). Do NOT call any more "
                        f"tools — emit your final ## Test Summary as plain text now."
                    )
            else:
                err = result.get("error") or result.get("stderr") or result.get("stdout") or "Unknown error"
                result["error_summary"] = (
                    f"Simulation failed. Check {log_name}.\n{err[:500]}"
                )
                result["stdout"] = adapter.filter_sim_output(result.get("stdout", ""))
                result["stderr"] = adapter.filter_sim_output(result.get("stderr", ""))

            return result
        except Exception as e:
            logging.error(f"v3 gen_{gen_id} simulation error: {e}")
            return {"success": False, "error": str(e)}

    # Closure-bound parse tools: read-only, NO merging into the global cumulative.
    # The dispatch cumulative is already maintained incrementally by run_simulation,
    # and the run-level cumulative is owned solely by orc_gen.update_state_node.
    from ...tools.analysis import _create_annotated_source

    @tool
    def parse_coverage(coverage_db_path: str) -> Dict[str, Any]:
        """Parse a coverage database without modifying any other DB.

        Pass the per-round DB returned by `run_simulation` to see what that
        round alone covers, OR pass `dispatch_cumulative_db_path` to see your
        rolling progress for this dispatch (seeded from the run-level
        cumulative at dispatch start, plus everything you have closed since).

        Args:
            coverage_db_path: Path to a UCDB file inside this dispatch's work
                directory.

        Returns:
            success, total_coverage, breakdown, annotated_source.
        """
        try:
            db_path = Path(coverage_db_path).resolve()
            if not db_path.exists():
                return {"success": False, "error": f"Coverage database not found: {coverage_db_path}"}

            cov_result = adapter.parse_coverage(db_path)
            max_holes = getattr(config, 'num_feedback_holes', 3)
            annotated_source = _create_annotated_source(
                cov_result.uncovered_lines, max_holes
            )
            return {
                "success": True,
                "total_coverage": cov_result.total_coverage,
                "iteration_coverage": cov_result.total_coverage,
                "cumulative_coverage": cov_result.total_coverage,
                "breakdown": cov_result.breakdown,
                "annotated_source": annotated_source,
                "coverage_db_path": str(db_path),
            }
        except Exception as e:
            logging.error(f"v3 gen_{gen_id} parse_coverage error: {e}")
            return {"success": False, "error": str(e)}

    @tool
    def parse_functional_coverage(coverage_db_path: str) -> Dict[str, Any]:
        """Parse a functional coverage database without modifying any other DB.

        Pass the per-round DB or `dispatch_cumulative_db_path`. Returns
        covergroup-level coverage and uncovered bins.
        """
        try:
            db_path = Path(coverage_db_path).resolve()
            if not db_path.exists():
                return {"success": False, "error": f"Coverage database not found: {coverage_db_path}"}

            result = adapter.parse_functional_coverage(db_path)
            if 'error' in result:
                return {"success": False, "error": result['error']}

            covergroups = result.get('covergroups', [])
            all_uncovered_bins = []
            for cg in covergroups:
                for bin_entry in cg.get('uncovered_bins', []):
                    if isinstance(bin_entry, dict):
                        all_uncovered_bins.append({
                            'covergroup': cg['name'],
                            'instance_path': cg.get('instance_path', ''),
                            'coverpoint': bin_entry.get('coverpoint', ''),
                            'coverpoint_kind': bin_entry.get('coverpoint_kind', 'Coverpoint'),
                            'bin_name': bin_entry.get('bin_name', ''),
                            'covergroup_coverage': cg.get('coverage', 0.0),
                            'sample_event': cg.get('sample_event'),
                        })
                    else:
                        all_uncovered_bins.append({
                            'covergroup': cg['name'], 'bin_name': bin_entry,
                        })
            return {
                "success": True,
                "total_coverage": result['total_coverage'],
                "iteration_coverage": result['total_coverage'],
                "cumulative_coverage": result['total_coverage'],
                "covergroups": covergroups,
                "uncovered_bins": all_uncovered_bins,
                "coverage_db_path": str(db_path),
            }
        except Exception as e:
            logging.error(f"v3 gen_{gen_id} parse_functional_coverage error: {e}")
            return {"success": False, "error": str(e)}

    tools = [read_file, write_file, compile_design, run_simulation, parse_coverage]
    if func_cov_enabled:
        tools.append(parse_functional_coverage)

    return tools, retry_state


# ----------------------------------------------------------------------------
# Dispatch entry point
# ----------------------------------------------------------------------------

def dispatch_test_generator_v3(
    config: Config,
    mode: str,
    task_description: str,
    testplan: str,
    target_module: str,
    module_header: str,
    design_files_access: List[str],
    coverage_context: str,
    iteration: int,
    gen_id: int,
) -> dict:
    """Run one v3 Test Generator dispatch and extract its Test Summary.

    Args:
        config: Application configuration.
        mode: "crt" or "directed".
        task_description: Short imperative description from the orchestrator.
        testplan: Full testplan text the orchestrator authored.
        target_module: Target DUT module ("top" or submodule name).
        module_header: Verilog module header for the target.
        design_files_access: Whitelist of file paths the generator may read.
        coverage_context: Optional short prose summary of remaining holes.
        iteration: Current orchestrator iteration.
        gen_id: Unique generator ID for this dispatch.

    Returns:
        Test Summary dict consumed by the orchestrator's update_state_node.
    """
    mode = mode.lower().strip()
    if mode not in ("crt", "directed"):
        return {
            "success": False,
            "summary": f"Invalid mode: {mode!r} (expected 'crt' or 'directed').",
            "mode": mode,
            "gen_id": gen_id,
            "target_module": target_module,
            "testbench_path": None,
            "coverage_db_path": None,
            "iterations_completed": 0,
            "final_iteration_coverage": 0.0,
        }

    logging.info(
        f"v3 dispatch: gen_{gen_id} mode={mode} target={target_module} "
        f"iter={iteration}"
    )
    emit("test_generator_v3_dispatch", {
        "gen_id": gen_id,
        "iteration": iteration,
        "mode": mode,
        "target_module": target_module,
        "task_preview": task_description[:200],
        "allowed_files": list(design_files_access or []),
    })

    try:
        tools, retry_state = make_generator_v3_tools(
            config, iteration, gen_id, mode, design_files_access or [],
        )

        llm_kwargs = dict(
            model=config.test_generator_model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            api_key=config.openai_api_key,
        )
        if config.reasoning_effort != "disabled":
            llm_kwargs["reasoning_effort"] = config.reasoning_effort

        system_prompt = load_orc_gen_test_generator_prompt(
            mode=mode,
            design_name=config.design_name,
            spec_path=str(config.spec_path),
            allowed_files=list(design_files_access or []),
            gen_max_iterations=config.gen_max_iterations,
            gen_max_retries=config.gen_max_retries,
            sim_timeout=config.sim_timeout,
        )

        agent = create_agent(
            model=ChatOpenAI(**llm_kwargs),
            tools=tools,
            system_prompt=system_prompt,
            name=f"test_generator_v3_{gen_id}",
        )

        # Build the task message
        tb_filename_hint = f"tb_iter_{iteration}_gen_{gen_id}_round_<N>.sv"
        func_cov_enabled = getattr(config, 'functional_coverage_enabled', False)
        func_cov_tb = getattr(config, 'functional_coverage_testbench_path', None)

        task_parts: List[str] = [
            f"## Task\n{task_description}",
            f"\n## Mode: {mode}",
            f"\n## Target Module: {target_module}",
            f"\n## Module Header\n```verilog\n{module_header}\n```",
        ]
        if testplan:
            task_parts.append(f"\n## Testplan\n{testplan}")
        if coverage_context:
            task_parts.append(f"\n## Current Coverage Context\n{coverage_context}")

        if design_files_access:
            allowed_block = "\n".join(f"  - {p}" for p in design_files_access)
        else:
            allowed_block = "  (none — operate purely from this task message)"
        task_parts.append(f"\n## Allowed read_file Paths\n{allowed_block}")

        task_parts.append(
            f"\n## Iteration Budget\n"
            f"- Up to {config.gen_max_iterations} successful coverage rounds.\n"
            f"- Up to {config.gen_max_retries} compile/sim failures total.\n"
            f"- Suggested filename pattern: `testbenches/{tb_filename_hint}`."
        )

        if func_cov_enabled and func_cov_tb:
            task_parts.append(
                f"\n## Functional Coverage Mode — STIMULUS BODY ONLY\n"
                f"Testbench template: `{func_cov_tb}`. Write ONLY the body lines "
                f"of the initial block to your testbench file — no `initial begin`, "
                f"no `$finish;`, no `end`, no module wrapper. The framework will "
                f"inject your lines into the template before compile."
            )

        task_parts.append(
            "\n## Workflow Reminder\n"
            "1. Plan and write the round-N testbench with `write_file`.\n"
            "2. `compile_design(<path>)`. On error, fix and retry (within retry budget).\n"
            "3. `run_simulation(testbench_name=\"tb_llm\")`. On error, fix and retry.\n"
            "4. `parse_coverage(<coverage_db_path>)` to inspect what this round added.\n"
            "5. If you have rounds left and useful uncovered space remains, "
            "loop back with a *different* testbench targeting different stimulus.\n"
            "6. When the framework signals you're done (via run_simulation's "
            "`framework_notice` or a retry-exhausted error), stop calling tools and "
            "emit the final `## Test Summary` plain-text response."
        )
        task_message = "\n".join(task_parts)

        recursion_limit = max(
            config.gen_recursion_limit,
            config.gen_max_iterations * 12 + (config.gen_max_retries + 1) * 6 + 20,
        )

        conv_logger = make_generator_logger(iteration, gen_id)
        conv_logger.agent_name = f"test_generator_v3_iter_{iteration}_gen_{gen_id}"
        conv_logger.log_path = (
            conv_logger.log_path.parent
            / f"test_generator_v3_iter_{iteration}_gen_{gen_id}.log"
        )

        result = agent.invoke(
            {"messages": [HumanMessage(content=task_message)]},
            config={"recursion_limit": recursion_limit, "callbacks": [conv_logger]},
        )

        return _extract_v3_summary(
            result=result,
            retry_state=retry_state,
            mode=mode,
            gen_id=gen_id,
            iteration=iteration,
            target_module=target_module,
            tb_dir_relative=f"testbenches/tb_iter_{iteration}_gen_{gen_id}_round_*.sv",
        )

    except Exception as e:
        logging.error(f"v3 dispatch_test_generator gen_{gen_id} error: {e}", exc_info=True)
        emit("test_generator_v3_error", {
            "gen_id": gen_id,
            "iteration": iteration,
            "mode": mode,
            "error": str(e),
        })
        return {
            "success": False,
            "summary": f"v3 generator dispatch raised: {e}",
            "mode": mode,
            "gen_id": gen_id,
            "target_module": target_module,
            "testbench_path": None,
            "coverage_db_path": None,
            "iterations_completed": 0,
            "final_iteration_coverage": 0.0,
        }


# ----------------------------------------------------------------------------
# Result extraction
# ----------------------------------------------------------------------------

def _extract_v3_summary(
    result: dict,
    retry_state: dict,
    mode: str,
    gen_id: int,
    iteration: int,
    target_module: str,
    tb_dir_relative: str,
) -> dict:
    """Parse the agent's message history into the orchestrator's expected payload."""
    messages = result.get("messages", [])

    # Final test summary text: last AIMessage with non-empty content
    summary_text = ""
    for msg in reversed(messages):
        if type(msg).__name__ == "AIMessage" and getattr(msg, "content", ""):
            summary_text = msg.content if isinstance(msg.content, str) else str(msg.content)
            break

    # Last successful sim result — drives final coverage and last testbench
    last_round_db: Optional[str] = retry_state.get("last_round_db")
    last_tb_path: Optional[str] = None
    final_round_coverage: float = 0.0
    successful_rounds = retry_state.get("successful_rounds", 0)

    for msg in reversed(messages):
        if not hasattr(msg, "name"):
            continue
        if msg.name == "run_simulation":
            try:
                content = msg.content
                parsed = json.loads(content) if isinstance(content, str) else content
            except (TypeError, ValueError):
                parsed = None
            if isinstance(parsed, dict) and parsed.get("success"):
                if not last_round_db:
                    last_round_db = parsed.get("coverage_db_path")
                break

    for msg in reversed(messages):
        if hasattr(msg, "tool_calls") and getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                args = tc.get("args", {}) or {}
                if tc.get("name") == "compile_design" and "testbench_path" in args:
                    last_tb_path = args["testbench_path"]
                    break
            if last_tb_path:
                break

    # Try to derive last-round coverage from a parse_coverage tool result
    for msg in reversed(messages):
        if hasattr(msg, "name") and msg.name in ("parse_coverage", "parse_functional_coverage"):
            try:
                content = msg.content
                parsed = json.loads(content) if isinstance(content, str) else content
            except (TypeError, ValueError):
                parsed = None
            if isinstance(parsed, dict):
                cov = (
                    parsed.get("cumulative_coverage")
                    or parsed.get("total_coverage")
                    or 0.0
                )
                try:
                    final_round_coverage = float(cov)
                except (TypeError, ValueError):
                    final_round_coverage = 0.0
                break

    dispatch_cumulative_db = retry_state.get("dispatch_cumulative_db")
    coverage_db_for_orchestrator: Optional[str] = None
    if dispatch_cumulative_db and Path(dispatch_cumulative_db).exists():
        coverage_db_for_orchestrator = dispatch_cumulative_db
    elif last_round_db and Path(last_round_db).exists():
        coverage_db_for_orchestrator = last_round_db

    success = successful_rounds > 0 and coverage_db_for_orchestrator is not None

    payload = {
        "success": success,
        "mode": mode,
        "gen_id": gen_id,
        "target_module": target_module,
        "testbench_path": last_tb_path,
        "coverage_db_path": coverage_db_for_orchestrator,
        "iterations_completed": successful_rounds,
        "summary": summary_text or (
            f"v3 generator gen_{gen_id} ({mode}) completed "
            f"{successful_rounds} successful round(s); "
            f"reason={retry_state.get('rounds_terminated_reason') or 'agent_finished'}."
        ),
        "final_iteration_coverage": final_round_coverage,
        "rounds_terminated_reason": retry_state.get("rounds_terminated_reason"),
    }

    emit("test_generator_v3_result", {
        "gen_id": gen_id,
        "iteration": iteration,
        "mode": mode,
        "success": success,
        "successful_rounds": successful_rounds,
        "coverage_db_path": coverage_db_for_orchestrator,
        "summary_preview": (summary_text or "")[:200],
    })

    logging.info(
        f"v3 gen_{gen_id} ({mode}) result: "
        f"{'SUCCESS' if success else 'FAILED'} "
        f"rounds={successful_rounds}/{retry_state.get('successful_rounds')} "
        f"db={coverage_db_for_orchestrator}"
    )

    return payload
