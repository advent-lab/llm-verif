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
from pathlib import Path


class _StripAnsiFilter(logging.Filter):
    """Logging filter that strips ANSI escape codes from log messages."""
    _ansi_re = re.compile(r'\033\[[0-9;]*m')

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._ansi_re.sub('', str(record.msg))
        return True


def _load_dotenv_local(env_path: Path, override: bool = True) -> None:
    """Minimal .env loader to avoid external dependencies."""
    with env_path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key   = key.strip()
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
    """Load environment variables from specified file."""
    env_path = Path(env_file_path).resolve()
    if not env_path.exists():
        raise FileNotFoundError(f"Environment file not found: {env_path}")

    _load_dotenv_local(env_path, override=True)
    print(f" Loaded environment from: {env_path}")

    simulator = os.getenv("SIMULATOR",    "not set")
    compiler  = os.getenv("COMPILER",     "not set")
    design    = os.getenv("DESIGN_NAME",  "not set")
    combined  = os.getenv("COMBINED_COVERAGE_ENABLED", "0")

    print(f"  - SIMULATOR:                 {simulator}")
    print(f"  - COMPILER:                  {compiler}")
    print(f"  - DESIGN_NAME:               {design}")
    print(f"  - COMBINED_COVERAGE_ENABLED: {combined}")
    print()


def validate_environment() -> None:
    """Validate that required environment variables are set."""
    required = {
        "COMPILER":       "Path to simulator binaries",
        "SIMULATOR":      "Simulator type (questasim or verilator)",
        "DESIGN_NAME":    "Design name",
        "DASHBOARD_PATH": "Path to dashboard.json",
    }

    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not set in env file")
        print("   Make sure it's set in your environment or the agent will fail")
        print()

    # In combined mode, FUNCTIONAL_COVERAGE_TESTBENCH is also required
    if os.getenv("COMBINED_COVERAGE_ENABLED", "0") == "1":
        if not os.getenv("FUNCTIONAL_COVERAGE_TESTBENCH"):
            print("❌ COMBINED_COVERAGE_ENABLED=1 requires FUNCTIONAL_COVERAGE_TESTBENCH to be set")
            raise ValueError("FUNCTIONAL_COVERAGE_TESTBENCH not set for combined coverage mode")

    missing = []
    for var, description in required.items():
        if not os.getenv(var):
            missing.append(f"  - {var}: {description}")

    if missing:
        print("❌ Missing required environment variables:")
        for m in missing:
            print(m)
        raise ValueError("Required environment variables not set")


def _print_artifacts(work_path: Path) -> None:
    """Print generated artifacts for a given work directory."""
    testbench_dir = work_path / "testbenches"
    logs_dir      = work_path / "logs"
    coverage_dir  = work_path / "coverage"

    if testbench_dir.exists():
        testbenches = list(testbench_dir.glob("*.sv")) + list(testbench_dir.glob("*.v"))
        print(f"  Testbenches:   {len(testbenches)} files in {testbench_dir}")
        for tb in sorted(testbenches)[:5]:
            print(f"    - {tb.name}")
        if len(testbenches) > 5:
            print(f"    ... and {len(testbenches) - 5} more")
    else:
        print(f"  Testbenches:   None generated")

    if logs_dir.exists():
        logs = list(logs_dir.glob("*.log"))
        print(f"  Logs:          {len(logs)} files in {logs_dir}")
    else:
        print(f"  Logs:          None generated")

    if coverage_dir.exists():
        cov_files = list(coverage_dir.glob("*"))
        print(f"  Coverage data: {len(cov_files)} files in {coverage_dir}")
    else:
        print(f"  Coverage data: None generated")


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

        load_env_file(args.env_file)

        print("Validating configuration...")
        validate_environment()
        print(" Configuration valid")
        print()

        if args.validate_only:
            print("Validation complete (--validate-only specified)")
            return 0

        langgraph_dir = Path(__file__).parent
        if str(langgraph_dir) not in sys.path:
            sys.path.insert(0, str(langgraph_dir))

        from src.graphs.react import create_react_graph
        from src.config import load_config
        import logging

        config = load_config()

        config.work_dir.mkdir(parents=True, exist_ok=True)

        log_file = config.work_dir / "run.log"

        console_formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
        file_formatter    = logging.Formatter('%(asctime)s - %(levelname)s:%(name)s:%(message)s')

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(getattr(logging, config.log_level))

        # File handler (ANSI color codes stripped for clean file output)
        file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
        file_handler.addFilter(_StripAnsiFilter())
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(getattr(logging, config.log_level))

        logging.root.handlers = []
        logging.root.addHandler(console_handler)
        logging.root.addHandler(file_handler)
        logging.root.setLevel(getattr(logging, config.log_level))

        # ── Print execution configuration ───────────────────────────────────
        print("=" * 70)
        print("AGENT EXECUTION CONFIGURATION")
        print("=" * 70)
        print(f"LLM:                       {config.model}")
        print(f"Work directory:            {config.work_dir}")
        print(f"Design:                    {config.design_name}")
        print(f"Design dir:                {config.design_dir}")
        print(f"Simulator:                 {config.simulator_type}")
        print(f"Simulator path:            {config.simulator_path}")
        print(f"Max iterations:            {config.max_iterations}")
        print(f"Max no progress:           {config.max_no_progress}")
        print(f"Sim runs:                  {config.sim_runs}")
        print(f"Sim timeout:               {config.sim_timeout} seconds")
        print(f"Log level:                 {config.log_level}")
        print(f"Log file:                  {log_file}")
        if config.combined_coverage_enabled:
            print(f"Combined coverage mode:    ENABLED")
            print(f"  Phase 1 dir:             {config.work_dir}")
            func_tb = os.getenv("FUNCTIONAL_COVERAGE_TESTBENCH", "N/A")
            print(f"  Phase 2 testbench:       {func_tb}")
        else:
            print(f"Functional coverage:       {'ENABLED' if config.functional_coverage_enabled else 'DISABLED'}")
        if config.uvm_enabled:
            print(f"UVM coverage mode:         {config.uvm_coverage_mode}")
        print("=" * 70)

        # ── Verify design structure ─────────────────────────────────────────
        print("\nVerifying design structure...")
        if not config.spec_path.exists():
            print(f"❌ Specification not found: {config.spec_path}")
            return 1

        if not config.design_files:
            print(f"❌ No design files found")
            return 1

        print(f" Found specification: {config.spec_path.name}")
        print(f" Found {len(config.design_files)} design file(s): "
              f"{', '.join(f.name for f in config.design_files)}")
        if config.design_context_files:
            print(f" Found {len(config.design_context_files)} context file(s)")

        # ── Run ─────────────────────────────────────────────────────────────
        print("\n" + "=" * 70)
        print("STARTING AGENT EXECUTION")
        print("=" * 70)

        if config.combined_coverage_enabled:
            print("\nThe agent will:")
            print("  Phase 1 - Code Coverage:")
            print("    1. Read and analyse the specification")
            print("    2. Generate full testbenches from scratch")
            print("    3. Iterate until code coverage target or termination condition")
            print("  Phase 2 - Functional Coverage:")
            print("    4. Read the provided testbench template")
            print("    5. Generate stimulus targeting uncovered bins")
            print("    6. Iterate until functional coverage target or termination condition")
        else:
            print("\nThe agent will:")
            print("  1. Read and analyze the specification")
            print("  2. Generate testbenches to cover spec requirements")
            print("  3. Compile and simulate testbenches")
            print("  4. Analyze coverage and identify gaps")
            print("  5. Iterate until coverage target or max iterations reached")

        print("\n" + "-" * 70)

        try:
            graph  = create_react_graph()
            result = graph.invoke(
                {"messages": []},
                config={"recursion_limit": config.recursion_limit}
            )

            final_state = result

            # ── Summary ─────────────────────────────────────────────────────
            print("\n" + "=" * 70)
            print("EXECUTION COMPLETE")
            print("=" * 70)

            # Save final state to JSON for visualization
            work_path = Path(final_state.get('work_dir', config.work_dir))
            serializable = {k: v for k, v in final_state.items() if k != 'messages'}
            if 'config' in serializable and serializable['config'] is not None:
                config_dict = dataclasses.asdict(serializable['config'])
                config_dict.pop('openai_api_key', None)
                serializable['config'] = config_dict
            state_path = work_path / "final_state.json"
            with open(state_path, 'w') as f:
                json.dump(serializable, f, indent=2, default=str)
            print(f"\nFinal state saved: {state_path}")

            if config.combined_coverage_enabled:
                # ── Combined mode: print both phases ────────────────────────
                code_summary = final_state.get("code_coverage_summary") or {}

                print("\n── Phase 1: Code Coverage ──────────────────────────────────")
                print(f"  Design:            {final_state.get('design_name', 'N/A')}")
                print(f"  Iterations:        {code_summary.get('iteration', 'N/A')}")
                print(f"  Max Coverage:      {code_summary.get('max_coverage', 0.0):.1f}%")
                print(f"  Merged Coverage:   {code_summary.get('cumulative_coverage', 0.0):.1f}%")
                print(f"  Work Directory:    {code_summary.get('work_dir', 'N/A')}")

                print("\n── Phase 2: Functional Coverage ────────────────────────────")
                print(f"  Design:            {final_state.get('design_name', 'N/A')}")
                print(f"  Iterations:        {final_state.get('iteration', 0)}")
                print(f"  Max Func Coverage: {final_state.get('max_functional_coverage', 0.0):.1f}%")
                print(f"  Termination:       {final_state.get('done_reason', 'N/A')}")
                print(f"  Work Directory:    {final_state.get('work_dir', 'N/A')}")

                print("\n── Artifacts ───────────────────────────────────────────────")
                phase1_dir = Path(code_summary.get("work_dir", ""))
                phase2_dir = Path(final_state.get("work_dir", config.work_dir))

                if phase1_dir.exists():
                    print(f"\n  Phase 1 ({phase1_dir.name}):")
                    _print_artifacts(phase1_dir)

                if phase2_dir.exists():
                    print(f"\n  Phase 2 ({phase2_dir.name}):")
                    _print_artifacts(phase2_dir)

            else:
                # ── Single-mode summary (unchanged) ─────────────────────────
                print(f"\nDesign:            {final_state.get('design_name', 'N/A')}")
                print(f"Iterations:        {final_state.get('iteration', 0)}")
                print(f"Max Coverage:      {final_state.get('max_coverage', 0):.1f}%")
                print(f"Merged Coverage:   {final_state.get('cumulative_coverage', 0):.1f}%")
                print(f"Termination:       {final_state.get('done_reason', 'N/A')}")
                print(f"Work Directory:    {final_state.get('work_dir', config.work_dir)}")

                print("\n" + "-" * 70)
                print("GENERATED ARTIFACTS")
                print("-" * 70)
                _print_artifacts(Path(final_state.get('work_dir', config.work_dir)))

            print("=" * 70)
            return 0

        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            print("\n" + "=" * 70)
            print("❌ EXECUTION FAILED")
            print("=" * 70)
            print(f"\nError: {e}")
            print(tb_str)
            # Also log to file so run.log always has the traceback
            logging.error(f"EXECUTION FAILED: {e}\n{tb_str}")
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
        import traceback
        tb_str = traceback.format_exc()
        print(f"❌ Unexpected error: {e}")
        print(tb_str)
        return 1


if __name__ == "__main__":
    sys.exit(main())
