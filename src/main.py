import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

from src.graphs.react import create_react_graph
from src.config import load_config

def main():
    """Main entry point for Spec2Cov."""

    # Load environment
    load_dotenv()

    # Setup logging
    config = load_config()

    # Configure basic logging
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Starting Spec2Cov for design: {config.design_dir.name}")
    logger.info(f"Work directory: {config.work_dir}")

    # Create and run graph
    try:
        graph = create_react_graph()
        result = graph.invoke(
            {"messages": []},
            config={"recursion_limit": config.recursion_limit}
        )

        logger.info("Verification complete")

        # Print summary
        final_state = result
        print("\n" + "="*80)
        print("VERIFICATION SUMMARY")
        print("="*80)
        print(f"Design: {final_state.get('design_name', 'N/A')}")
        print(f"Iterations: {final_state.get('iteration', 0)}")
        print(f"Final Coverage: {final_state.get('current_coverage', 0):.1f}%")
        print(f"Max Coverage: {final_state.get('max_coverage', 0):.1f}%")
        print(f"Done Reason: {final_state.get('done_reason', 'N/A')}")
        print(f"Work Directory: {final_state.get('work_dir', 'N/A')}")
        print("="*80)

    except Exception as e:
        logger.error(f"Verification failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
