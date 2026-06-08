"""events.jsonl writer — append-only, atomic per line, thread-safe."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, TypedDict


class Event(TypedDict, total=False):
    timestamp: str
    run_id: str
    iteration: int | None
    node: str | None
    agent_id: str | None
    dispatch_id: str | None
    kind: str
    payload: dict


def iso_now() -> str:
    now = datetime.now(timezone.utc).astimezone()
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}" + now.strftime("%z")


class EventLogger:
    def __init__(self, events_path: Path, run_id: str) -> None:
        self._path = Path(events_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._run_id = run_id
        self._lock = threading.Lock()
        self._fh: IO[str] | None = self._path.open("a", buffering=1, encoding="utf-8")

    def emit(
        self,
        kind: str,
        payload: dict | None = None,
        *,
        iteration: int | None = None,
        node: str | None = None,
        agent_id: str | None = None,
        dispatch_id: str | None = None,
    ) -> Event:
        event: Event = {
            "timestamp": iso_now(),
            "run_id": self._run_id,
            "iteration": iteration,
            "node": node,
            "agent_id": agent_id,
            "dispatch_id": dispatch_id,
            "kind": kind,
            "payload": payload or {},
        }
        line = json.dumps(event, default=str, ensure_ascii=False) + "\n"
        with self._lock:
            if self._fh is None:
                raise RuntimeError("EventLogger is closed")
            self._fh.write(line)
        return event

    def close(self) -> None:
        with self._lock:
            if self._fh is not None:
                self._fh.flush()
                self._fh.close()
                self._fh = None

    def __enter__(self) -> EventLogger:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
