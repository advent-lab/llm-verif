"""Per-agent conversation file logging via LangChain callbacks.

Logs agent conversations in a chat-style transcript format:
each message appears exactly once, appended incrementally.

Format mirrors a ChatGPT/Claude chat:
  [SYSTEM]
  ...system prompt...

  [HUMAN]
  ...user message...

  [ASSISTANT | In: 3,421 | Cached: 0 | Out: 423 | Total: 3,844]
  ...reasoning...
    → dispatch_crt_agent({"task_description": "..."})

  [TOOL: dispatch_crt_agent]
  {"success": true, ...}

  [ASSISTANT | In: 4,100 | Cached: 3,421 | Out: 212 | Total: 4,312]
  Coverage looks good. Wrapping up.

Usage:
    from src.utils.conversation_logger import (
        init_conversation_logging,
        get_logger,
        make_generator_logger,
    )

    init_conversation_logging(config.work_dir)   # once at session start

    # Pass callback at LLM invoke time:
    llm.invoke(messages, config={"callbacks": [get_logger("orchestrator")]})
    expert_graph.invoke(input, config={"configurable": {...}, "callbacks": [get_logger("design_expert")]})
    gen_agent.invoke(input, config={"callbacks": [make_generator_logger(iteration, gen_id)]})
"""

import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

_log_dir: Optional[Path] = None
_handlers: Dict[str, "ConversationLogger"] = {}
_init_lock = threading.Lock()

_TRUNCATE_LIMIT = 10000


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def init_conversation_logging(work_dir: Path) -> None:
    """Initialize conversation logging. Call once at session start."""
    global _log_dir, _handlers
    with _init_lock:
        _log_dir = Path(work_dir) / "conversations"
        _log_dir.mkdir(parents=True, exist_ok=True)
        _handlers = {}


# ---------------------------------------------------------------------------
# Public factory functions
# ---------------------------------------------------------------------------

def get_logger(agent_name: str) -> "ConversationLogger":
    """Return the singleton ConversationLogger for agent_name."""
    with _init_lock:
        if agent_name not in _handlers:
            log_dir = _log_dir or Path(".")
            _handlers[agent_name] = ConversationLogger(agent_name, log_dir)
        return _handlers[agent_name]


def make_generator_logger(iteration: int, gen_id: int) -> "ConversationLogger":
    """Create a fresh ConversationLogger for a single generator dispatch.

    Returns a new instance (not a singleton) writing to
    conversations/test_generator_iter_{N}_gen_{M}.log
    """
    agent_name = f"test_generator_iter_{iteration}_gen_{gen_id}"
    log_dir = _log_dir or Path(".")
    return ConversationLogger(agent_name, log_dir)


# ---------------------------------------------------------------------------
# ConversationLogger callback handler
# ---------------------------------------------------------------------------

class ConversationLogger(BaseCallbackHandler):
    """Logs LLM conversations as incremental chat transcripts.

    Each message is written exactly once in the order it appears:
      - on_chat_model_start: writes any new non-AI messages (SYSTEM, HUMAN, TOOL)
        that have accumulated since the last turn
      - on_llm_end: writes the new AI response with token metrics

    Thread-safe per instance via a lock.
    """

    raise_error = False

    def __init__(self, agent_name: str, log_dir: Path) -> None:
        super().__init__()
        self.agent_name = agent_name
        self.log_path = Path(log_dir) / f"{agent_name}.log"
        self._lock = threading.Lock()
        # Number of messages already written to the log.
        # Tracks position in the accumulated message list so only deltas are written.
        self._written = 0

    # -----------------------------------------------------------------------
    # LLM hooks
    # -----------------------------------------------------------------------

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[Any]],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Write any new non-AI messages since the last turn."""
        try:
            flat = messages[0] if messages else []

            # Clamp in case messages were pruned (e.g. prune_context / RemoveMessage)
            self._written = min(self._written, len(flat))

            new_msgs = flat[self._written:]
            parts = []
            for msg in new_msgs:
                formatted = _format_incoming_message(msg)
                if formatted:
                    parts.append(formatted)

            self._written = len(flat)

            if parts:
                self._write("\n".join(parts))

        except Exception as e:
            logging.debug(f"ConversationLogger.on_chat_model_start error: {e}")

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Write the AI response with token metrics."""
        try:
            tokens = _extract_tokens(response)

            gen = None
            if response.generations and response.generations[0]:
                gen = response.generations[0][0]

            if gen is None:
                return

            msg = getattr(gen, "message", None)
            content = ""
            tool_calls = []

            if msg is not None:
                content = _get_content_text(msg)
                tool_calls = getattr(msg, "tool_calls", []) or []
            elif hasattr(gen, "text"):
                content = gen.text or ""

            header = (
                f"[ASSISTANT | "
                f"In: {tokens['input']:,} | "
                f"Cached: {tokens['cached']:,} | "
                f"Out: {tokens['output']:,} | "
                f"Total: {tokens['total']:,}]"
            )
            if tokens['reasoning']:
                header = header[:-1] + f" | Reasoning: {tokens['reasoning']:,}]"

            parts = [header]

            if content:
                parts.append(_truncate(content))

            for tc in tool_calls:
                name = tc.get("name", "unknown")
                args = tc.get("args", {})
                parts.append(f"  → {name}({_truncate(json.dumps(args, default=str), 500)})")

            parts.append("")  # trailing blank line

            self._write("\n".join(parts) + "\n")
            self._written += 1  # account for the new AI message added to state

        except Exception as e:
            logging.debug(f"ConversationLogger.on_llm_end error: {e}")

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _write(self, text: str) -> None:
        with self._lock:
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(text)
            except Exception as e:
                logging.debug(f"ConversationLogger file write error: {e}")


# ---------------------------------------------------------------------------
# Message formatting helpers
# ---------------------------------------------------------------------------

def _format_incoming_message(msg: Any) -> str:
    """Format a non-AI message (SYSTEM, HUMAN, TOOL) as a chat entry."""
    msg_type = type(msg).__name__

    if msg_type == "SystemMessage":
        return f"[SYSTEM]\n{_truncate(_get_content_text(msg))}\n"

    elif msg_type == "HumanMessage":
        return f"[HUMAN]\n{_truncate(_get_content_text(msg))}\n"

    elif msg_type == "ToolMessage":
        tool_name = getattr(msg, "name", "unknown") or "unknown"
        content = msg.content if hasattr(msg, "content") else ""
        return f"[TOOL: {tool_name}]\n{_truncate(_format_tool_content(content))}\n"

    elif msg_type == "AIMessage":
        # AI messages that appear in history (from prior turns) — these were
        # already written via on_llm_end; skip them to avoid duplication.
        return ""

    # Skip RemoveMessage and other internal types
    return ""


def _get_content_text(msg: Any) -> str:
    content = getattr(msg, "content", "")
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and "text" in part:
                parts.append(part["text"])
            elif isinstance(part, str):
                parts.append(part)
        return "\n".join(parts)
    return str(content) if content else ""


def _format_tool_content(content: Any) -> str:
    if not isinstance(content, str):
        content = str(content)
    try:
        parsed = json.loads(content)
        return json.dumps(parsed, indent=2, default=str)
    except (json.JSONDecodeError, TypeError):
        return content


def _truncate(text: str, limit: int = _TRUNCATE_LIMIT) -> str:
    if not isinstance(text, str):
        text = str(text)
    if limit and len(text) > limit:
        return text[:limit] + f"\n... [{len(text):,} chars total, truncated]"
    return text


def _extract_tokens(response: LLMResult) -> Dict[str, int]:
    defaults = {"input": 0, "output": 0, "total": 0, "reasoning": 0, "cached": 0}
    try:
        if not response.generations or not response.generations[0]:
            return defaults
        gen = response.generations[0][0]
        msg = getattr(gen, "message", None)
        if msg is None:
            return defaults
        usage = getattr(msg, "usage_metadata", None) or {}
        return {
            "input": usage.get("input_tokens", 0),
            "output": usage.get("output_tokens", 0),
            "total": usage.get("total_tokens", 0),
            "reasoning": (usage.get("output_token_details") or {}).get("reasoning", 0),
            "cached": (usage.get("input_token_details") or {}).get("cache_read", 0),
        }
    except Exception:
        return defaults
