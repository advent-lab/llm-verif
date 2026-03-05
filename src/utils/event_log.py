"""Structured JSONL event logging for the ReAct verification framework.

Provides a comprehensive, machine-parseable event log (events.jsonl) that
captures every framework step: session lifecycle, API calls, tool executions,
state transitions, and routing decisions. Modeled after Codex CLI's JSONL
logging format for cross-framework comparability.

Usage:
    from src.utils.event_log import init_event_log, emit

    init_event_log(Path("work/run1/events.jsonl"))
    emit("session_start", {"model": "o3", "design": "trng_top", ...})
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class EventLog:
    """Writes structured JSONL events to a file.

    Each line is a JSON object: {"ts": "<ISO 8601>", "event": "<type>", "data": {...}}
    Flushes after every write for crash safety.
    """

    def __init__(self, log_path: Path):
        self._path = Path(log_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self._path, "a", encoding="utf-8")

    def emit(self, event: str, data: dict) -> None:
        """Write one event line to the JSONL log."""
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "data": data,
        }
        line = json.dumps(record, default=_json_default, ensure_ascii=False)
        self._file.write(line + "\n")
        self._file.flush()

    def close(self) -> None:
        """Flush and close the log file."""
        if self._file and not self._file.closed:
            self._file.flush()
            self._file.close()

    @property
    def path(self) -> Path:
        return self._path


# ---------------------------------------------------------------------------
# Module-level singleton (same pattern as set_tool_config)
# ---------------------------------------------------------------------------

_event_log: Optional[EventLog] = None


def init_event_log(log_path: Path) -> EventLog:
    """Initialize the global event log. Call once at session start."""
    global _event_log
    _event_log = EventLog(log_path)
    return _event_log


def get_event_log() -> Optional[EventLog]:
    """Return the global event log (or None if not initialized)."""
    return _event_log


def emit(event: str, data: dict) -> None:
    """Emit an event to the global log. No-op if log is not initialized."""
    if _event_log is not None:
        _event_log.emit(event, data)


def close_event_log() -> None:
    """Close the global event log."""
    global _event_log
    if _event_log is not None:
        _event_log.close()
        _event_log = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_default(obj: Any) -> Any:
    """JSON serializer fallback for non-standard types."""
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, set):
        return list(obj)
    if hasattr(obj, "__dict__"):
        return str(obj)
    return str(obj)


def serialize_message(msg) -> dict:
    """Serialize a LangChain message to a JSON-safe dict.

    Captures type, role, content, tool calls, tool call ID, and name —
    everything needed to reconstruct the conversation from the log.
    """
    msg_type = type(msg).__name__
    result = {"type": msg_type}

    if hasattr(msg, "content"):
        result["content"] = msg.content
        if isinstance(msg.content, str):
            result["content_length"] = len(msg.content)
        elif isinstance(msg.content, list):
            result["content_length"] = sum(
                len(c.get("text", "")) if isinstance(c, dict) else len(str(c))
                for c in msg.content
            )

    if hasattr(msg, "name") and msg.name:
        result["name"] = msg.name

    if hasattr(msg, "tool_call_id") and msg.tool_call_id:
        result["tool_call_id"] = msg.tool_call_id

    if hasattr(msg, "tool_calls") and msg.tool_calls:
        result["tool_calls"] = [
            {
                "name": tc.get("name", "unknown"),
                "args": tc.get("args", {}),
                "id": tc.get("id", ""),
            }
            for tc in msg.tool_calls
        ]

    if hasattr(msg, "response_metadata") and msg.response_metadata:
        result["response_metadata"] = msg.response_metadata

    return result


def serialize_config(config) -> dict:
    """Serialize a Config object to a JSON-safe dict with all parameters."""
    return {
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "max_iterations": config.max_iterations,
        "max_retries": config.max_retries,
        "max_no_progress": config.max_no_progress,
        "context_window": config.context_window,
        "sim_runs": config.sim_runs,
        "sim_timeout": config.sim_timeout,
        "num_feedback_holes": config.num_feedback_holes,
        "coverage_hole_radius": config.coverage_hole_radius,
        "recursion_limit": config.recursion_limit,
        "log_level": config.log_level,
        "log_truncate": config.log_truncate,
        "design_name": config.design_name,
        "design_dir": str(config.design_dir),
        "spec_path": str(config.spec_path),
        "design_files": [str(f) for f in config.design_files],
        "design_context_files": [str(f) for f in config.design_context_files],
        "design_context_enabled": config.design_context_enabled,
        "testplan_enabled": config.testplan_enabled,
        "work_dir": str(config.work_dir),
        "run_id": config.run_id,
        "simulator_type": config.simulator_type,
        "simulator_path": str(config.simulator_path),
    }


def get_git_info() -> dict:
    """Capture current git branch and commit hash."""
    info = {}
    try:
        info["branch"] = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()
        info["commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return info
