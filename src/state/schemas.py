from typing import TypedDict, Annotated, Optional, List, Any, Dict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """State for the Spec2Cov ReAct agent."""

    # Message history with add_messages reducer
    messages: Annotated[list[BaseMessage], add_messages]

    # Configuration (loaded once during initialization)
    # Using Any to avoid circular import, but it's actually a Config object
    config: Any

    # Design context (set during initialization)
    design_name: str
    design_dir: str
    spec_path: str
    design_files: List[str]          # Main design RTL files (DUT)
    design_context_files: List[str]  # Supporting files (submodules/dependencies)
    rtl_dir: str                     # Deprecated - kept for compatibility
    module_header: str
    work_dir: str

    # Tracking
    iteration: int             # Increment after successful compile+sim+coverage cycle
    attempt: int               # Individual tool attempts - for unique log naming
    api_calls: int             # Total agent_node invocations (LLM API calls)
    consecutive_failures: int  # Compile OR sim failures in a row
    no_progress_count: int     # Consecutive cycles with no coverage improvement

    # Coverage tracking (Code Coverage)
    current_coverage: float          # Latest coverage % - single iteration
    max_coverage: float              # Best single-iteration coverage achieved
    cumulative_coverage: float       # Merged coverage across ALL iterations
    cumulative_coverage_db: Optional[str]  # Path to merged coverage database

    # Functional Coverage
    functional_coverage_enabled: bool            # True = stimulus generation mode
    functional_coverage_target: float            # Target functional coverage %
    functional_coverage_testbench_path: Optional[str]  # Path to user-provided testbench
    current_functional_coverage: float           # Latest functional coverage %
    max_functional_coverage: float               # Best functional coverage achieved
    functional_coverage_history: List[float]     # Track functional coverage per iteration
    uncovered_bins: List[Dict[str, Any]]         # List of uncovered bins with details

    # ── Combined Coverage Mode ──────────────────────────────────────────────
    # "code" during Phase 1, "functional" during Phase 2.
    # None when COMBINED_COVERAGE_ENABLED=0 (single-mode runs are unaffected).
    coverage_phase: Optional[str]

    # Snapshot of Phase 1 (code coverage) results saved at phase transition
    # so run_agent.py can print a summary for both phases at the end.
    code_coverage_summary: Optional[Dict[str, Any]]
    # ────────────────────────────────────────────────────────────────────────

    # UVM mode
    uvm_enabled: bool
    uvm_coverage_mode: str  # "functional" or "line"

    # Agent loop tracking
    consecutive_no_tool_calls: int  # Consecutive LLM responses with no tool calls

    # Infrastructure modification pipeline
    infra_modification_enabled: bool   # True = LLM may modify driver file
    original_driver_path: Optional[str]  # Path to original (unmodified) driver

    # Termination
    is_done: bool
    done_reason: Optional[str]
