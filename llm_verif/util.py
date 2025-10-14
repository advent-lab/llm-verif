"""
Utility module for LLM-based verification.

DEPRECATED: This module is being phased out. Its contents have been moved to:
- conversation_runner.py: For conversation orchestration
- metrics.py: For evaluation metrics (pass@k functions)

This file is kept temporarily for backward compatibility but may be removed
in future versions.
"""

# All functionality has been moved to specialized modules:
# - ConversationRunner in conversation_runner.py
# - Metrics functions in metrics.py

# For backward compatibility, you can import from the new locations:
# from llm_verif.conversation_runner import ConversationRunner
# from llm_verif.metrics import estimate_pass_at_k, pass_at_k
