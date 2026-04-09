#!/usr/bin/env python3
"""
LangGraph Agent Runner

Run the LangGraph verification framework with a specific environment configuration file.

Usage:
    python run_agent.py --env-file configs/verilator.env
    python run_agent.py -e configs/questasim.env
    python run_agent.py  # Uses default .env file

Examples:
    # Run with Verilator config
    python run_agent.py --env-file configs/verilator.env

    # Run with QuestaSim config
    python run_agent.py --env-file configs/questasim.env

    # Run with custom config
    python run_agent.py -e /path/to/my/custom.env
"""

import argparse
import dataclasses
import json
import logging
import os
import re
import sys
import time
from pathlib import Path


class _StripAnsiFilter(logging.Filter):
    """Logging filter that strips ANSI escape codes from log messages."""
    _ansi_re = re.compile(r'\033\[[0-9;]*m')

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._ansi_re.sub('', str(record.msg))
        return True


def _load_dotenv_local(env_path: Path, override: bool = True) -> None:
    """Minimal .env loader to avoid external dependencies.

    Supports lines in KEY=VALUE format, ignores blank lines and comments (# ...),
    and strips surrounding single/double quotes from values.
    """
    with env_path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()

            if not line or line.startswith("#"):
                continue

            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            if not key:
                continue

            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]

            if not override and key in os.environ:
                continue

            os.environ[key] = value


def load_env_file(env_file_path: str) -> None:
    """Load environment variables from specified file.

    Args:
        env_file_path: Path to .env file to load

    Raises:
        FileNotFoundError: If env file doesn't exist
    """
    env_path = Path(env_file_path).resolve()

    if not env_path.exists():
        raise FileNotFoundError(f"Environment file not found: {env_path}")

    # Load the specified env file
    _load_dotenv_local(env_path, override=True)
    print(f" Loaded environment from: {env_path}")

    # Print key configuration
    simulator = os.getenv("SIMULATOR", "not set")
    compiler = os.getenv("COMPILER", "not set")
    design = os.getenv("DESIGN_NAME", "not set")

    print(f"  - SIMULATOR: {simulator}")
    print(f"  - COMPILER: {compiler}")
    print(f"  - DESIGN_NAME: {design}")
    print()


def validate_environment() -> None:
    """Validate that required environment variables are set.

    Raises:
        ValueError: If required variables are missing
    """
    required = {
        "COMPILER": "Path to simulator binaries",
        "SIMULATOR": "Simulator type (questasim or verilator)",
        "DESIGN_NAME": "Design name",
        "DASHBOARD_PATH": "Path to dashboard.json",
    }

    # OPENAI_API_KEY is optional if already set
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not set in env file")
        print("   Make sure it's set in your environment or the agent will fail")
        print()

    missing = []
    for var, description in required.items():
        if not os.getenv(var):
            missing.append(f"  - {var}: {description}")

    if missing:
        print("❌ Missing required environment variables:")
        for m in missing:
            print(m)
        raise ValueError("Required environment variables not set")


def main():
    """Main entry point for the agent runner."""
    parser = argparse.ArgumentParser(
        description="Run LangGraph verification framework with specific config",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --env-file configs/verilator.env
  %(prog)s -e configs/questasim.env
  %(prog)s  # Uses default .env file

Environment File Format:
  COMPILER=/scratch/vpatel69/verilator/bin
  SIMULATOR=verilator
  DESIGN_NAME=fifo
  DASHBOARD_PATH=/home/vpatel69/capstone/dashboard.json
  OPENAI_API_KEY=sk-...
  SIM_RUNS=20
  MAX_ITERATIONS=10
        """
    )

    parser.add_argument(
        "-e", "--env-file",
        type=str,
        default=".env",
        help="Path to environment config file (default: .env)"
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate config without running agent"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    args = parser.parse_args()

    try:
        print("=" * 70)
        print("LangGraph Agent Runner")
        print("=" * 70)
        print()

        # Load environment file
        load_env_file(args.env_file)

        # Validate environment
        print("Validating configuration...")
        validate_environment()
        print(" Configuration valid")
        print()

        if args.validate_only:
            print("Validation complete (--validate-only specified)")
            return 0

        # Add LangGraph directory to path so src can import correctly
        langgraph_dir = Path(__file__).parent
        if str(langgraph_dir) not in sys.path:
            sys.path.insert(0, str(langgraph_dir))

        # Import framework modules
        from src.config import load_config
        import logging

        # Load configuration
        config = load_config()

        # Create work directory if it doesn't exist
        config.work_dir.mkdir(parents=True, exist_ok=True)

        # Setup logging with both console and file output
        log_file = config.work_dir / "run.log"
        
        # Create formatters
        console_formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s:%(name)s:%(message)s')
        
        # Console handler (with colors)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(getattr(logging, config.log_level))
        
        # File handler (ANSI color codes stripped for clean file output)
        file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
        file_handler.addFilter(_StripAnsiFilter())
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(getattr(logging, config.log_level))
        
        # Configure root logger
        logging.root.handlers = []  # Clear any existing handlers
        logging.root.addHandler(console_handler)
        logging.root.addHandler(file_handler)
        logging.root.setLevel(getattr(logging, config.log_level))

        # Print execution configuration
        print("=" * 70)
        print("AGENT EXECUTION CONFIGURATION")
        print("=" * 70)
        print(f"Architecture:     {config.architecture}")
        print(f"LLM:              {config.model}")
        if config.architecture == "v2":
            print(f"  Orchestrator:   {config.orchestrator_model}")
            print(f"  Design Expert:  {config.design_expert_model}")
            print(f"  Test Generator: {config.test_generator_model}")
        elif config.architecture == "v2.1":
            print(f"  Orchestrator:         {config.orchestrator_model}")
            print(f"  Analyzer-Generator:   {config.analyzer_generator_model}")
            print(f"  CRT:                  {config.crt_model}")
        print(f"Work directory:   {config.work_dir}")
        print(f"Design:           {config.design_name}")
        print(f"Design dir:       {config.design_dir}")
        print(f"Simulator:        {config.simulator_type}")
        print(f"Simulator path:   {config.simulator_path}")
        print(f"Max iterations:   {config.max_iterations}")
        print(f"Max no progress:  {config.max_no_progress}")
        print(f"Sim runs:         {config.sim_runs}")
        print(f"Sim timeout:      {config.sim_timeout} seconds")
        print(f"Log level:        {config.log_level}")
        print(f"Log file:         {log_file}")
        print("=" * 70)

        # Verify design structure
        print("\nVerifying design structure...")
        if not config.spec_path.exists():
            print(f"❌ Specification not found: {config.spec_path}")
            return 1

        if not config.design_files:
            print(f"❌ No design files found")
            return 1

        print(f" Found specification: {config.spec_path.name}")
        print(f" Found {len(config.design_files)} design file(s): {', '.join(f.name for f in config.design_files)}")
        if config.design_context_files:
            print(f" Found {len(config.design_context_files)} context file(s)")

        # Create and run graph
        print("\n" + "=" * 70)
        print("STARTING AGENT EXECUTION")
        print("=" * 70)
        print("\nThe agent will:")
        print("  1. Read and analyze the specification")
        print("  2. Generate testbenches to cover spec requirements")
        print("  3. Compile and simulate testbenches")
        print("  4. Analyze coverage and identify gaps")
        print("  5. Iterate until coverage target or max iterations reached")
        print("\n" + "-" * 70)

        start_time = time.monotonic()
        try:
            from src.utils.event_log import emit, close_event_log

            # Select architecture
            if config.architecture == "v2":
                from src.graphs.orc_exp_gen import create_multi_agent_graph
                from src.utils.conversation_logger import init_conversation_logging
                init_conversation_logging(config.work_dir)
                graph = create_multi_agent_graph()
            elif config.architecture == "v2.1":
                from src.graphs.ag_crt import create_ag_crt_graph
                from src.utils.conversation_logger import init_conversation_logging
                init_conversation_logging(config.work_dir)
                graph = create_ag_crt_graph()
            else:
                from src.graphs.react import create_react_graph
                graph = create_react_graph()
            result = graph.invoke(
                {"messages": []},
                config={"recursion_limit": config.recursion_limit}
            )

            duration_seconds = time.monotonic() - start_time

            # Print summary
            final_state = result
            print("\n" + "=" * 70)
            print("EXECUTION COMPLETE")
            print("=" * 70)
            print(f"\nDesign:            {final_state.get('design_name', 'N/A')}")
            print(f"Iterations:        {final_state.get('iteration', 0)}")
            print(f"Max Coverage:      {final_state.get('max_coverage', 0):.2f}%")
            print(f"Merged Coverage:    {final_state.get('cumulative_coverage', 0):.2f}%")
            print(f"Termination:       {final_state.get('done_reason', 'N/A')}")
            print(f"Work Directory:    {final_state.get('work_dir', config.work_dir)}")

            # Save final state to JSON for visualization
            work_path = Path(final_state.get('work_dir', config.work_dir))
            serializable = {k: v for k, v in final_state.items() if k not in ('messages',)}
            if 'config' in serializable and serializable['config'] is not None:
                config_dict = dataclasses.asdict(serializable['config'])
                config_dict.pop('openai_api_key', None)
                serializable['config'] = config_dict
            # Strip tool_call_args from token_usage records (verbose, not needed in JSON)
            if 'token_usage' in serializable and serializable['token_usage']:
                cleaned_records = []
                for rec in serializable['token_usage']:
                    rec_copy = {k: v for k, v in rec.items() if k != 'tool_call_args'}
                    cleaned_records.append(rec_copy)
                serializable['token_usage'] = cleaned_records
            state_path = work_path / "final_state.json"
            with open(state_path, 'w') as f:
                json.dump(serializable, f, indent=2, default=str)
            print(f"\nFinal state saved: {state_path}")

            # --- JSONL: agent_message + session_end ---
            summary_text = (
                f"Design: {final_state.get('design_name', 'N/A')}, "
                f"Iterations: {final_state.get('iteration', 0)}, "
                f"Final Coverage: {final_state.get('cumulative_coverage', 0):.2f}%, "
                f"Done Reason: {final_state.get('done_reason', 'N/A')}"
            )
            emit("agent_message", {"message": summary_text})

            token_usage = final_state.get("token_usage", [])
            total_input = sum(r.get("input_tokens", 0) for r in token_usage)
            total_output = sum(r.get("output_tokens", 0) for r in token_usage)
            total_reasoning = sum(r.get("reasoning_tokens", 0) for r in token_usage)
            total_cached = sum(r.get("cached_input_tokens", 0) for r in token_usage)
            total_all = sum(r.get("total_tokens", 0) for r in token_usage)

            emit("session_end", {
                "design_name": final_state.get("design_name"),
                "final_coverage": final_state.get("cumulative_coverage", 0.0),
                "max_coverage": final_state.get("max_coverage", 0.0),
                "iterations": final_state.get("iteration", 0),
                "total_api_calls": final_state.get("api_calls", 0),
                "done_reason": final_state.get("done_reason"),
                "duration_seconds": round(duration_seconds, 2),
                "tokens_summary": {
                    "input_tokens": total_input,
                    "output_tokens": total_output,
                    "reasoning_tokens": total_reasoning,
                    "cached_input_tokens": total_cached,
                    "total_tokens": total_all,
                    "cache_hit_rate": round(total_cached / total_input, 4) if total_input > 0 else 0.0,
                },
                "token_usage": token_usage,
            })
            close_event_log()

            # Check for generated artifacts
            work_path = Path(final_state.get('work_dir', config.work_dir))
            testbench_dir = work_path / "testbenches"
            logs_dir = work_path / "logs"
            coverage_dir = work_path / "coverage"

            print("\n" + "-" * 70)
            print("GENERATED ARTIFACTS")
            print("-" * 70)

            if testbench_dir.exists():
                testbenches = list(testbench_dir.glob("*.sv")) + list(testbench_dir.glob("*.v"))
                print(f"Testbenches:     {len(testbenches)} files in {testbench_dir}")
                for tb in sorted(testbenches)[:5]:  # Show first 5
                    print(f"  - {tb.name}")
                if len(testbenches) > 5:
                    print(f"  ... and {len(testbenches) - 5} more")
            else:
                print(f"Testbenches:     None generated")

            if logs_dir.exists():
                logs = list(logs_dir.glob("*.log"))
                print(f"Logs:            {len(logs)} files in {logs_dir}")
            else:
                print(f"Logs:            None generated")

            if coverage_dir.exists():
                cov_files = list(coverage_dir.glob("*"))
                print(f"Coverage data:   {len(cov_files)} files in {coverage_dir}")
            else:
                print(f"Coverage data:   None generated")

            print("=" * 70)
            return 0

        except Exception as e:
            duration_seconds = time.monotonic() - start_time
            print("\n" + "=" * 70)
            print("❌ EXECUTION FAILED")
            print("=" * 70)
            print(f"\nError: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()

            # --- JSONL: session_end on error ---
            try:
                emit("session_end", {
                    "error": str(e),
                    "duration_seconds": round(duration_seconds, 2),
                })
                close_event_log()
            except Exception:
                pass  # Don't let logging failure mask the real error

            return 1

    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print()
        print("Make sure the environment file exists.")
        print(f"Tried to load: {args.env_file}")
        return 1

    except ValueError as e:
        print(f"❌ Error: {e}")
        return 1

    except KeyboardInterrupt:
        print()
        print("⚠️  Interrupted by user")
        return 130

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
