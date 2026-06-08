"""Per-conversation transcript writers (init / orchestrate / per-agent)."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Literal

ConversationKind = Literal["init", "orchestrate", "agent"]


def _serialize(message: Any) -> dict:
    if isinstance(message, dict):
        return message
    # LangChain BaseMessage path
    if hasattr(message, "model_dump"):
        return message.model_dump()
    out: dict = {}
    for attr in ("type", "role", "content", "name", "tool_calls", "tool_call_id"):
        if hasattr(message, attr):
            out[attr] = getattr(message, attr)
    if not out:
        out = {"repr": repr(message)}
    return out


class ConversationLogger:
    def __init__(self, path: Path, kind: ConversationKind) -> None:
        self._path = Path(path)
        self._kind = kind
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, message: Any) -> None:
        if self._kind == "init":
            raise RuntimeError("init conversation uses write_initial(), not append()")
        line = json.dumps(_serialize(message), default=str, ensure_ascii=False) + "\n"
        with self._lock:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(line)

    def write_initial(self, messages: list[Any]) -> None:
        if self._kind != "init":
            raise RuntimeError("write_initial only valid for init conversation")
        body = [_serialize(m) for m in messages]
        with self._lock:
            self._path.write_text(
                json.dumps(body, indent=2, default=str, ensure_ascii=False)
            )
