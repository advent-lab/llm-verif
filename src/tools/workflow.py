from typing import Dict, Any
from langchain.tools import tool

@tool
def signal_done(reason: str) -> Dict[str, Any]:
    """
    Signal that you want to end the verification process.

    Args:
        reason: Why you're stopping. Must be one of:
            - "coverage_complete": Achieved 100% coverage
            - "no_progress": Made multiple attempts with no improvement
            - "max_iterations": Reached iteration limit

    Returns:
        Dictionary with success and message
    """
    valid_reasons = ["coverage_complete", "no_progress", "max_iterations"]

    if reason not in valid_reasons:
        return {
            "success": False,
            "message": f"Invalid reason. Must be one of: {valid_reasons}"
        }

    return {
        "success": True,
        "message": f"Verification complete: {reason}"
    }
