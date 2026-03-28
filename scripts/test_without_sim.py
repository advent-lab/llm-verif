"""Test script for running Spec2Cov without QuestaSim.

This script demonstrates how to test the agent flow using mock tools.
It validates ~70% of the framework functionality without requiring a simulator.

Usage:
    1. Configure .env.test with your design path and optional API key
    2. Run: python test_without_sim.py
    3. Check work_test/ directory for generated artifacts
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# CRITICAL: Set TEST_MODE before importing any framework modules
os.environ["TEST_MODE"] = "1"

def main():
    """Run framework in test mode."""

    # Load test environment
    test_env = Path(__file__).parent / ".env.test"
    if test_env.exists():
        load_dotenv(test_env)
        print(f"[OK] Loaded test environment from {test_env}")
    else:
        print(f"[ERROR] Test environment not found: {test_env}")
        print("\nSetup instructions:")
        print("  1. Copy the example: cp .env.test .env.test")
        print("  2. Edit .env.test and set DESIGN path")
        print("  3. Optionally set OPENAI_API_KEY for full agent testing")
        print("  4. Run this script again")
        return 1

    # Import framework modules AFTER setting TEST_MODE and loading .env
    try:
        from src.graphs.react import create_react_graph
        from src.config import load_config
    except ImportError as e:
        print(f"[X] Failed to import framework modules: {e}")
        print("\nMake sure you're running from the LangGraph directory")
        return 1

    # Load configuration
    try:
        config = load_config()
    except ValueError as e:
        print(f"[X] Configuration error: {e}")
        print("\nCheck your .env.test file:")
        print("  - DESIGN must point to a valid design directory")
        print("  - DESIGN directory must contain docs/ and rtl/ subdirectories")
        return 1

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Force set root logger level (basicConfig can be ignored if logging was already configured)
    logging.root.setLevel(getattr(logging, config.log_level))

    logger = logging.getLogger(__name__)

    # Print test configuration
    print("\n" + "="*80)
    print("SPEC2COV TEST MODE")
    print("="*80)
    print(f"Design:           {config.design_name}")
    print(f"Design dir:       {config.design_dir}")
    print(f"Work directory:   {config.work_dir}")
    print(f"Max iterations:   {config.max_iterations}")
    print(f"Sim runs:         {config.sim_runs}")
    print(f"Model:            {config.model}")
    print(f"API Key:          {'SET' if config.openai_api_key else 'NOT SET (graph-only mode)'}")
    print(f"Log level:        {config.log_level}")
    print("="*80)

    # Verify design structure (now using config values directly)
    spec_path = config.spec_path
    design_files = config.design_files
    design_context_files = config.design_context_files

    if not spec_path.exists():
        print(f"\n[X] Specification not found: {spec_path}")
        print("  Check your DESIGN_NAME or DESIGN path in .env.test")
        return 1

    if not design_files:
        print(f"\n[X] No design files found")
        print("  Check your DESIGN_NAME or DESIGN path in .env.test")
        return 1

    print(f"\n[OK] Found specification: {spec_path.name}")
    print(f"[OK] Found {len(design_files)} design file(s): {', '.join(f.name for f in design_files)}")
    if design_context_files:
        print(f"[OK] Found {len(design_context_files)} context file(s): {', '.join(f.name for f in design_context_files)}")

    # Check if we have API key for full testing
    if not config.openai_api_key:
        print("\n! WARNING: OPENAI_API_KEY not set")
        print("  This will test graph structure only")
        print("  For full agent testing, set your API key in .env.test")
        print("\nDo you want to continue with graph-only testing? (y/n): ", end="")

        response = input().strip().lower()
        if response != 'y':
            print("Aborted. Set OPENAI_API_KEY in .env.test and try again.")
            return 0

    # Create and run graph
    try:
        print("\n" + "="*80)
        print("STARTING TEST EXECUTION")
        print("="*80)
        print("\n--> Creating ReAct graph...")
        graph = create_react_graph()
        print("[OK] Graph created successfully")

        print("\n--> Starting agent execution...")
        print("\nThe agent will:")
        print("  1. Initialize environment and read specification")
        print("  2. Generate testbenches based on spec requirements")
        print("  3. Mock-compile testbenches (validates syntax)")
        print("  4. Mock-simulate testbenches (generates fake coverage)")
        print("  5. Analyze mock coverage and iterate")
        print("  6. Continue until coverage target or max iterations reached")
        print("\n" + "-"*80)

        # Run the graph (initialize with empty messages list)
        # Set higher recursion_limit to accommodate multiple iterations with tool calls
        result = graph.invoke(
            {"messages": []},
            config={"recursion_limit": 100}
        )

        logger.info("Verification workflow complete")

        # Print summary
        final_state = result
        print("\n" + "="*80)
        print("TEST EXECUTION COMPLETE")
        print("="*80)

        # Extract state information
        design_name = final_state.get('design_name', 'N/A')
        iteration = final_state.get('iteration', 0)
        current_coverage = final_state.get('current_coverage', 0)
        max_coverage = final_state.get('max_coverage', 0)
        done_reason = final_state.get('done_reason', 'N/A')
        work_dir = final_state.get('work_dir', config.work_dir)

        print(f"\nDesign:            {design_name}")
        print(f"Iterations:        {iteration}")
        print(f"Final Coverage:    {current_coverage:.2f}% (MOCKED)")
        print(f"Max Coverage:      {max_coverage:.2f}%")
        print(f"Termination:       {done_reason}")
        print(f"Work Directory:    {work_dir}")

        # Check for generated artifacts
        work_path = Path(work_dir)
        testbench_dir = work_path / "testbenches"
        logs_dir = work_path / "logs"
        coverage_dir = work_path / "coverage"

        print("\n" + "-"*80)
        print("GENERATED ARTIFACTS")
        print("-"*80)

        if testbench_dir.exists():
            testbenches = list(testbench_dir.glob("*.sv")) + list(testbench_dir.glob("*.v"))
            print(f"[OK] Testbenches:     {len(testbenches)} files in {testbench_dir}")
            for tb in testbenches[:3]:  # Show first 3
                print(f"  - {tb.name}")
            if len(testbenches) > 3:
                print(f"  ... and {len(testbenches) - 3} more")
        else:
            print(f"[X] Testbenches:     None generated")

        if logs_dir.exists():
            logs = list(logs_dir.glob("*.log"))
            print(f"[OK] Logs:            {len(logs)} files in {logs_dir}")
        else:
            print(f"[X] Logs:            None generated")

        if coverage_dir.exists():
            ucdb_files = list(coverage_dir.glob("*.ucdb"))
            print(f"[OK] Coverage DBs:    {len(ucdb_files)} files in {coverage_dir}")
        else:
            print(f"[X] Coverage DBs:    None generated")

        print("\n" + "="*80)
        print("[OK] TEST EXECUTION SUCCESSFUL")
        print("="*80)
        print(f"\nNext steps:")
        print(f"  1. Review generated testbenches in: {testbench_dir}")
        print(f"  2. Check mock logs in: {logs_dir}")
        print(f"  3. Examine agent reasoning in the output above")
        print(f"\nNote: Coverage values are MOCKED for testing purposes.")
        print(f"      Use real QuestaSim for actual verification.")

        return 0

    except Exception as e:
        logger.error(f"Test execution failed: {e}", exc_info=True)
        print("\n" + "="*80)
        print("[X] TEST EXECUTION FAILED")
        print("="*80)
        print(f"\nError: {e}")
        print("\nCheck the logs above for details.")
        print("\nCommon issues:")
        print("  - Missing or invalid DESIGN path")
        print("  - Missing docs/specification.md or rtl/ files")
        print("  - Invalid OPENAI_API_KEY (if set)")
        print("  - Python dependencies not installed (pip install -r requirements.txt)")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
