#!/usr/bin/env python3
"""
LangGraph-based LLM Verification Framework (Main Entry Point)

This is the new main entry point that uses LangGraph for multi-agent orchestration.
It replaces the linear pipeline in llm_verif.py with a graph-based approach.

Usage:
    python llm_verif_langgraph.py \
        --design designs/counter \
        --compiler iverilog \
        --id test_langgraph \
        --simulator verilator \
        --backend openai \
        --max_iterations 20

New Features:
    - Multi-agent system (Planner, Generator, Critic, Grader, Refiner)
    - Pre-simulation quality gates (Critic agent)
    - Rich feedback (Grader agent)
    - Adaptive routing based on state
    - Built-in observability
"""

import asyncio
import argparse
import logging
import os
import sys
from typing import Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from llm_verif.environment import Environment
from llm_verif.record import Record
from llm_verif.openai_backend import OpenAIBackend
from llm_verif.llama3_chat import LlamaChat
from llm_verif.langgraph_framework import create_verification_graph, VerificationState


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="LangGraph-based LLM Verification Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Required arguments
    parser.add_argument("--design", required=True, help="Path to design directory")
    parser.add_argument("--compiler", required=True, help="Compiler to use (iverilog, verilator, etc.)")
    parser.add_argument("--id", required=True, help="Unique identifier for this run")
    parser.add_argument("--simulator", required=True, choices=["questasim", "verilator"], help="Simulator to use")
    parser.add_argument("--backend", default="openai", choices=["openai", "vllm"], help="LLM backend")

    # LLM configuration
    parser.add_argument("--dotenv_path", type=str, required=False, default=".env", help="Path to dotenv file containing API keys")
    parser.add_argument("--base_url", default=None, help="Base URL for OpenAI-compatible API")
    parser.add_argument("--api_key", default=None, help="API key (or use OPENAI_API_KEY env var)")
    parser.add_argument("--model", type=str, default="gpt-4o", help="Model ID (default: gpt-4o)")
    parser.add_argument("--tokenizer", type=str, default="meta-llama/Llama-3.3-70B-Instruct", help="Tokenizer for conversation management")
    parser.add_argument("-q", "--quantize", action="store_true", default=False, help="Enable quantization")

    # Iteration control
    parser.add_argument("--max_iterations", type=int, default=50, help="Maximum total iterations")
    parser.add_argument("--max_valid_iter", type=int, default=20, help="Maximum successful iterations")
    parser.add_argument("--runs", type=int, default=1, help="Number of independent runs")

    # Generation parameters
    parser.add_argument("--temperature", type=float, default=0.7, help="LLM temperature")
    parser.add_argument("--temperature_function", default="constant",
                        choices=["constant", "logarithmic", "capped_sigmoid"],
                        help="Temperature scheduling function")
    parser.add_argument("--batch_size", type=int, default=1, help="Number of testbenches to generate per iteration")

    # Features
    parser.add_argument("--testplan", action="store_true", help="Enable verification plan generation (Planner agent)")
    parser.add_argument("--remove_polluted_context", action="store_true", help="Enable context slicing")
    parser.add_argument("--no_design_prompt", action="store_true", help="Disable full design files in prompts")
    parser.add_argument("--zero_shot", action="store_true", help="Zero-shot mode (no examples)")
    parser.add_argument("--crt", action="store_true", help="Constrained random testing mode")

    # LangGraph-specific
    parser.add_argument("--enable_critic", action="store_true", default=True, help="Enable Critic agent (default: True)")
    parser.add_argument("--enable_grader", action="store_true", default=True, help="Enable Grader agent (default: True)")
    parser.add_argument("--disable_critic", action="store_true", help="Disable Critic agent")
    parser.add_argument("--disable_grader", action="store_true", help="Disable Grader agent")
    parser.add_argument("--visualize_graph", action="store_true", help="Generate graph visualization")

    # Simulator options
    parser.add_argument("--sim_runs", type=int, default=1, help="Number of simulation runs per testbench")
    parser.add_argument("--merge_coverage", action="store_true", help="Merge coverage across iterations")

    # Output
    parser.add_argument("--work_dir", default="./work", help="Working directory for artifacts")
    parser.add_argument("-o", "--output", type=str, default="./output", help="Output directory for log files")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    return parser.parse_args()


async def run_single_verification(
    graph,
    environment: Environment,
    record: Record,
    args: argparse.Namespace,
    run_index: int
) -> VerificationState:
    """
    Run a single verification workflow using LangGraph.

    Args:
        graph: Compiled LangGraph application
        environment: Environment with design info
        record: Record for tracking metrics
        args: Command-line arguments
        run_index: Current run index

    Returns:
        Final state after graph execution
    """
    logging.info(f"{'='*80}")
    logging.info(f"RUN {run_index + 1}/{args.runs}: {environment.design_name}")
    logging.info(f"{'='*80}")

    # Build initial state
    initial_state: VerificationState = {
        # Design context
        "design_name": environment.design_name,
        "design_spec": environment.design_specification,
        "module_header": environment.module_header,
        "design_files": environment.all_design_file_paths,
        "design_module_name": environment.design_module_name,

        # Conversation history
        "messages": [],

        # Planning
        "verification_plan": {},
        "plan_available": False,

        # Generation
        "current_testbench": "",
        "current_testbench_comments": "",
        "generated_testbenches": [],
        "generation_count": 0,
        "batch_candidates": [],

        # Critique
        "critique_results": {},
        "critique_enabled": args.enable_critic and not args.disable_critic,

        # Simulation
        "simulation_results": {},
        "simulation_success": True,

        # Grading
        "grading_results": {},
        "grading_enabled": args.enable_grader and not args.disable_grader,

        # Iteration tracking
        "iteration": 0,
        "valid_iterations": 0,
        "max_coverage": 0.0,
        "coverage_history": [],

        # Metrics
        "run_index": run_index,
        "tokens_generated": 0,
        "total_generation_time": 0.0,
        "simulator_calls": 0,
        "critic_rejections": 0,

        # Configuration
        "max_iterations": args.max_iterations,
        "max_valid_iter": args.max_valid_iter,
        "batch_size": args.batch_size,
        "temperature": args.temperature,
        "testplan_enabled": args.testplan,
        "remove_polluted_context": args.remove_polluted_context,
        "no_design_prompt": args.no_design_prompt,
        "crt": args.crt,
        "sim_runs": args.sim_runs,

        # Control flow
        "next_action": "continue",
        "first_success": False,

        # File paths
        "work_dir": args.work_dir,
        "csv_path": environment.csv_path
    }

    # Execute graph
    logging.info("[Main] Starting LangGraph execution...")

    try:
        # Stream events for real-time monitoring
        final_state = None

        # Configure recursion limit (default is 25, increase for more iterations)
        config = {"recursion_limit": 100}

        async for event in graph.astream(initial_state, config=config):
            # Event is a dict with node name as key
            node_name = list(event.keys())[0]
            node_state = event[node_name]

            # Log progress
            iteration = node_state.get("iteration", 0)
            coverage = node_state.get("max_coverage", 0.0)

            logging.info(
                f"[{node_name.upper()}] Iteration {iteration}, "
                f"Coverage: {coverage:.2f}%, "
                f"Sim Calls: {node_state.get('simulator_calls', 0)}"
            )

            final_state = node_state

        if final_state is None:
            logging.error("[Main] Graph execution failed - no final state!")
            return initial_state

        # Log final results
        logging.info(f"{'='*80}")
        logging.info(f"RUN {run_index + 1} COMPLETE")
        logging.info(f"  Max Coverage: {final_state.get('max_coverage', 0.0):.2f}%")
        logging.info(f"  Iterations: {final_state.get('iteration', 0)}")
        logging.info(f"  Valid Iterations: {final_state.get('valid_iterations', 0)}")
        logging.info(f"  Simulator Calls: {final_state.get('simulator_calls', 0)}")
        logging.info(f"  Critic Rejections: {final_state.get('critic_rejections', 0)}")
        logging.info(f"  Tokens Generated: {final_state.get('tokens_generated', 0)}")
        logging.info(f"  Generation Time: {final_state.get('total_generation_time', 0.0):.2f}s")
        logging.info(f"{'='*80}")

        # Finalize record for this run
        from llm_verif.langgraph_framework.utils.record_integration import finalize_run_record, save_record
        finalize_run_record(record, run_index)
        save_record(record, f"./{final_state.get('csv_path', 'results.csv')}")

        return final_state

    except Exception as e:
        logging.error(f"[Main] Error during graph execution: {e}")
        raise


async def main():
    """Main entry point."""
    args = parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    logging.info("="*80)
    logging.info("LangGraph-based LLM Verification Framework")
    logging.info("="*80)

    # Load environment
    logging.info("[Main] Loading environment...")
    environment = Environment(args)

    # Create record (match original system's constructor)
    record = Record(
        environment.design_name,
        identifier=args.id,
        temp_func=args.temperature_function,
        testplan=args.testplan,
        batch_size=args.batch_size,
        remove_polluted_context=args.remove_polluted_context,
        run_type="RUN",
        include_merge_coverage=args.merge_coverage
    )

    # Create simulator first (needed for LLM backend)
    logging.info(f"[Main] Initializing {args.simulator} simulator...")

    if args.simulator == "questasim":
        from llm_verif.questasim import QuestaSim
        simulator = QuestaSim(args.compiler, environment.design_module_name)
    else:  # verilator
        from llm_verif.verilator import Verilator
        simulator = Verilator(args.compiler, environment.design_module_name)

    # Create LLM backend
    logging.info(f"[Main] Initializing {args.backend} backend...")

    if args.backend == "openai":
        llm_backend = OpenAIBackend(
            simulator=simulator,
            environment=environment,
            do_sample=True,  # Enable sampling by default
            temperature_function=args.temperature_function,
            temperature=args.temperature,
            top_p=0.7,
            max_new_tokens=4098,
            timeout_seconds=1000,
            seed=None,
            base_url=args.base_url,
            api_key=args.api_key or os.getenv("OPENAI_API_KEY")
        )
    else:  # vllm
        llm_backend = LlamaChat(
            simulator=simulator,
            environment=environment,
            do_sample=True,
            temperature_function=args.temperature_function,
            temperature=args.temperature
        )

    # Create graph
    logging.info("[Main] Building LangGraph...")
    graph = create_verification_graph(llm_backend, simulator, environment, args, record)

    # Visualize graph (optional)
    if args.visualize_graph:
        from llm_verif.langgraph_framework.graph import visualize_graph
        visualize_graph(graph, output_path=f"{args.work_dir}/verification_graph.mmd")

    # Run verification for each run
    for run_index in range(args.runs):
        final_state = await run_single_verification(
            graph, environment, record, args, run_index
        )

    # Write final record
    record.write_to_csv(f"./{environment.csv_path}")

    logging.info("="*80)
    logging.info("ALL RUNS COMPLETE")
    logging.info(f"Results saved to: {environment.csv_path}")
    logging.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
