from typing import TypedDict, Annotated, Optional, List, Any, Dict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """State for the Spec2Cov ReAct agent."""

    # Message history with add_messages reducer
    messages: Annotated[list[BaseMessage], add_messages]

    # Configuration (loaded once during initialization)
    # Using Any to avoid circular import, but it's actually a Config object
    config: Any  # Add config to state to avoid repeated loading

    # Design context (set during initialization)
    design_name: str
    design_dir: str
    spec_path: str
    design_files: List[str]  # Main design RTL files (DUT)
    design_context_files: List[str]  # Supporting files (submodules/dependencies)
    rtl_dir: str  # Deprecated - kept for compatibility, use design_files instead
    module_header: str
    work_dir: str

    # Tracking
    iteration: int  # Increment after successful compile+sim+coverage cycle (coverage improves)
    attempt: int  # Individual tool attempts (compile or sim calls) - for unique log naming
    api_calls: int  # Total agent_node invocations (LLM API calls) - for max_iterations limit
    consecutive_failures: int  # Compilation OR simulation failures in a row - for max_retries limit
    no_progress_count: int  # Consecutive cycles with no coverage improvement - for max_no_progress limit

    # Coverage tracking (Code Coverage)
    current_coverage: float  # Latest coverage percentage (0-100) - single iteration
    max_coverage: float  # Best single-iteration coverage achieved
    cumulative_coverage: float  # Merged coverage across ALL iterations
    cumulative_coverage_db: Optional[str]  # Path to merged coverage database file

    # Functional Coverage (NEW)
    functional_coverage_enabled: bool  # True = stimulus generation mode, False = full testbench mode
    functional_coverage_target: float  # Target functional coverage % (default 100.0)
    functional_coverage_testbench_path: Optional[str]  # Path to user-provided testbench with covergroups
    current_functional_coverage: float  # Latest functional coverage % (0-100)
    max_functional_coverage: float  # Best functional coverage achieved
    functional_coverage_history: List[float]  # Track functional coverage per iteration
    uncovered_bins: List[Dict[str, Any]]  # List of uncovered bins with details

    # Termination
    is_done: bool
    done_reason: Optional[str]  # "coverage_complete", "no_progress", "max_iterations"     
