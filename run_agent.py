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
import os
import sys
from pathlib import Path


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
        from src.graphs.react import create_react_graph
        from src.config import load_config
        import logging

        # Load configuration
        config = load_config()

        # Setup logging
        logging.basicConfig(
            level=getattr(logging, config.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logging.root.setLevel(getattr(logging, config.log_level))

        # Print execution configuration
        print("=" * 70)
        print("AGENT EXECUTION CONFIGURATION")
        print("=" * 70)
        print(f"LLM:              {config.model}")
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

        try:
            graph = create_react_graph()
            result = graph.invoke(
                {"messages": []},
                config={"recursion_limit": 100}
            )

            # Print summary
            final_state = result
            print("\n" + "=" * 70)
            print("EXECUTION COMPLETE")
            print("=" * 70)
            print(f"\nDesign:            {final_state.get('design_name', 'N/A')}")
            print(f"Iterations:        {final_state.get('iteration', 0)}")
            print(f"Final Coverage:    {final_state.get('current_coverage', 0):.1f}%")
            print(f"Max Coverage:      {final_state.get('max_coverage', 0):.1f}%")
            print(f"Termination:       {final_state.get('done_reason', 'N/A')}")
            print(f"Work Directory:    {final_state.get('work_dir', config.work_dir)}")

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
            print("\n" + "=" * 70)
            print("❌ EXECUTION FAILED")
            print("=" * 70)
            print(f"\nError: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
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
