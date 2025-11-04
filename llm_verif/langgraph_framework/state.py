"""
LangGraph State Schema for Verification Framework

Defines the central state object that flows through all agents.
"""

from typing import TypedDict, List, Dict, Any, Annotated, Optional
import operator


class VerificationState(TypedDict):
    """
    Central state object for the LangGraph verification workflow.

    Uses Annotated with operator.add for append-only fields (messages, history).
    State updates are merged into the existing state, not replaced.
    """

    # ============================================================================
    # DESIGN CONTEXT
    # ============================================================================
    design_name: str
    design_spec: str
    module_header: str
    design_files: List[str]
    design_module_name: str

    # ============================================================================
    # CONVERSATION HISTORY (append-only)
    # ============================================================================
    messages: Annotated[List[Dict[str, str]], operator.add]

    # ============================================================================
    # PLANNING
    # ============================================================================
    verification_plan: Dict[str, Any]
    plan_available: bool

    # ============================================================================
    # GENERATION
    # ============================================================================
    current_testbench: str
    current_testbench_comments: str
    generated_testbenches: Annotated[List[Dict[str, Any]], operator.add]
    generation_count: int
    batch_candidates: List[str]

    # ============================================================================
    # CRITIQUE (NEW AGENT)
    # ============================================================================
    critique_results: Dict[str, Any]  # score, issues, recommendation
    critique_enabled: bool

    # ============================================================================
    # SIMULATION
    # ============================================================================
    simulation_results: Dict[str, Any]
    simulation_success: bool

    # ============================================================================
    # GRADING (NEW AGENT)
    # ============================================================================
    grading_results: Dict[str, Any]  # grade, scores, analysis
    grading_enabled: bool

    # ============================================================================
    # ITERATION TRACKING
    # ============================================================================
    iteration: int
    valid_iterations: int
    max_coverage: float
    coverage_history: Annotated[List[float], operator.add]

    # ============================================================================
    # METRICS & TRACKING
    # ============================================================================
    run_index: int
    tokens_generated: int
    total_generation_time: float
    simulator_calls: int
    critic_rejections: int

    # ============================================================================
    # CONFIGURATION
    # ============================================================================
    max_iterations: int
    max_valid_iter: int
    batch_size: int
    temperature: float
    testplan_enabled: bool
    remove_polluted_context: bool
    no_design_prompt: bool
    crt: bool  # Constrained random testing
    sim_runs: int

    # ============================================================================
    # CONTROL FLOW
    # ============================================================================
    next_action: str  # For routing decisions
    first_success: bool  # Track first successful generation

    # ============================================================================
    # FILE PATHS
    # ============================================================================
    work_dir: str
    csv_path: str


# Helper functions for state manipulation

def get_recent_messages(state: VerificationState, max_tokens: int = 15000) -> List[Dict[str, str]]:
    """
    Get recent messages that fit within token limit.
    Mimics ConversationManager's pruning logic.
    """
    from transformers import AutoTokenizer

    messages = state.get("messages", [])
    if not messages:
        return []

    # Keep system message
    system_msg = messages[0] if messages and messages[0]["role"] == "system" else None
    user_assistant_pairs = messages[1:] if system_msg else messages

    # Simple token counting (rough approximation)
    # In production, use actual tokenizer
    total_chars = sum(len(msg["content"]) for msg in user_assistant_pairs)

    # Rough estimate: 1 token ≈ 4 characters
    estimated_tokens = total_chars / 4

    # Prune oldest pairs if needed
    while estimated_tokens > max_tokens and len(user_assistant_pairs) > 2:
        user_assistant_pairs = user_assistant_pairs[2:]  # Remove oldest pair
        total_chars = sum(len(msg["content"]) for msg in user_assistant_pairs)
        estimated_tokens = total_chars / 4

    if system_msg:
        return [system_msg] + user_assistant_pairs
    return user_assistant_pairs


def slice_messages_from_first_success(state: VerificationState) -> List[Dict[str, str]]:
    """
    Slice messages to keep only: system + first success + latest messages.
    Mimics ConversationManager's stack pointer slicing.
    """
    messages = state.get("messages", [])
    if not messages or not state.get("first_success"):
        return messages

    # Find index of first successful generation
    # This would be tracked in state metadata
    # For now, return recent messages
    return get_recent_messages(state, max_tokens=15000)


def build_conversation_context(state: VerificationState) -> List[Dict[str, str]]:
    """
    Build conversation context for LLM, applying token limits and slicing.
    """
    if state.get("remove_polluted_context") and state.get("first_success"):
        return slice_messages_from_first_success(state)
    else:
        return get_recent_messages(state, max_tokens=15000)
