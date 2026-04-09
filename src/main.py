import logging
import os
import sys
import time
from dotenv import load_dotenv

from src.config import load_config
from src.utils.event_log import emit, close_event_log

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

    # Select architecture
    architecture = getattr(config, 'architecture', 'v1')
    if architecture == "v2":
        from src.graphs.orc_exp_gen import create_multi_agent_graph
        from src.utils.conversation_logger import init_conversation_logging
        logger.info("Using v2 multi-agent architecture (Orchestrator-Expert-Generator)")
        init_conversation_logging(config.work_dir)
        graph = create_multi_agent_graph()
    elif architecture == "v2.1":
        from src.graphs.ag_crt import create_ag_crt_graph
        from src.utils.conversation_logger import init_conversation_logging
        logger.info("Using v2.1 multi-agent architecture (Orchestrator → Analyzer-Generator + CRT)")
        init_conversation_logging(config.work_dir)
        graph = create_ag_crt_graph()
    else:
        from src.graphs.react import create_react_graph
        logger.info("Using v1 single-agent architecture (ReAct)")
        graph = create_react_graph()

    # Create and run graph
    start_time = time.monotonic()
    try:
        result = graph.invoke(
            {"messages": []},
            config={"recursion_limit": config.recursion_limit}
        )

        duration_seconds = time.monotonic() - start_time
        logger.info("Verification complete")

        # Print summary
        final_state = result
        summary_text = (
            f"Design: {final_state.get('design_name', 'N/A')}, "
            f"Iterations: {final_state.get('iteration', 0)}, "
            f"Final Coverage: {final_state.get('cumulative_coverage', 0):.2f}%, "
            f"Done Reason: {final_state.get('done_reason', 'N/A')}"
        )

        print("\n" + "="*80)
        print("VERIFICATION SUMMARY")
        print("="*80)
        print(f"Design: {final_state.get('design_name', 'N/A')}")
        print(f"Iterations: {final_state.get('iteration', 0)}")
        print(f"Final Coverage: {final_state.get('cumulative_coverage', 0):.2f}%")
        print(f"Max Coverage: {final_state.get('max_coverage', 0):.2f}%")
        print(f"Done Reason: {final_state.get('done_reason', 'N/A')}")
        print(f"Work Directory: {final_state.get('work_dir', 'N/A')}")
        print(f"Duration: {duration_seconds:.2f}s")
        print("="*80)

        # --- JSONL: agent_message + session_end ---
        emit("agent_message", {"message": summary_text})

        # Compute token totals from token_usage records
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

    except Exception as e:
        duration_seconds = time.monotonic() - start_time
        logger.error(f"Verification failed: {e}", exc_info=True)

        # --- JSONL: session_end on error ---
        emit("session_end", {
            "error": str(e),
            "duration_seconds": round(duration_seconds, 2),
        })
        close_event_log()

        sys.exit(1)

if __name__ == "__main__":
    main()
