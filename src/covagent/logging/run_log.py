"""Human-readable run.log — rendered from the same event stream as events.jsonl."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import IO

from covagent.logging.events import Event, EventLogger


def _ts(event: Event) -> str:
    return event.get("timestamp", "").replace("T", " ")[:23]


def _fmt(event: Event) -> str:
    kind = event.get("kind", "")
    payload = event.get("payload", {}) or {}
    iteration = event.get("iteration")
    ts = _ts(event)

    if kind == "run.started":
        return f"{ts}  run.started  {payload.get('run_id', '')}"
    if kind == "run.ended":
        return (
            f"{ts}  run.ended    status={payload.get('run_status')} "
            f"iters={payload.get('iterations')} dispatches={payload.get('total_dispatches')} "
            f"wall={payload.get('wall_time_s'):.1f}s"
            if isinstance(payload.get("wall_time_s"), (int, float))
            else f"{ts}  run.ended    status={payload.get('run_status')}"
        )
    if kind == "node.entered":
        return f"{ts}  {payload.get('node')}: entered (iter={iteration})"
    if kind == "node.exited":
        dur = payload.get("duration_s")
        dur_s = f" ({dur:.2f}s)" if isinstance(dur, (int, float)) else ""
        return f"{ts}  {payload.get('node')}: exited{dur_s}"
    if kind == "agent.spawned":
        return (
            f"{ts}    spawn  {payload.get('agent_id')}   "
            f"feature={payload.get('feature_label')}  "
            f"scope={payload.get('scope_items')}"
        )
    if kind == "agent.invoked":
        return (
            f"{ts}    resume  {payload.get('agent_id')}   "
            f"{payload.get('dispatch_id')}  budget={payload.get('attempt_budget')}"
        )
    if kind == "agent.signed_off":
        return f"{ts}    sign-off  {payload.get('agent_id')}  reason={payload.get('reason')}"
    if kind == "agent.retired":
        return f"{ts}    retired   {payload.get('agent_id')}  reason={payload.get('reason')}"
    if kind == "agent.errored":
        return f"{ts}    ERR  {payload.get('agent_id')}  {payload.get('error')}"
    if kind == "dispatch.scheduled":
        return (
            f"{ts}      {payload.get('dispatch_id')}  "
            f"agent={payload.get('agent_id')}  items={payload.get('item_names')}"
        )
    if kind == "dispatch.completed":
        return (
            f"{ts}      {payload.get('dispatch_id')}  completed  "
            f"stop={payload.get('stop_reason')}  wall={payload.get('wall_time_s')}s"
        )
    if kind == "dispatch.merge_failed":
        return f"{ts}      {payload.get('dispatch_id')}  merge_failed: {payload.get('error')}"
    if kind == "coverage.merged":
        return (
            f"{ts}  update_state: merged delta {payload.get('dispatch_id')} "
            f"in {payload.get('duration_s', 0):.2f}s"
        )
    if kind == "coverage.snapshot_taken":
        return (
            f"{ts}  coverage.snapshot iter={payload.get('iteration')} "
            f"-> {payload.get('path')}"
        )
    if kind == "coverage.queried":
        return f"{ts}  coverage.queried scope={payload.get('scope')} {payload.get('result_summary')}"
    if kind == "testplan.patched":
        return (
            f"{ts}  testplan.patched {payload.get('target_type')}/{payload.get('name')} "
            f"by={payload.get('by')} fields={payload.get('fields_changed')}"
        )
    if kind == "testplan.history_appended":
        return (
            f"{ts}  testplan.history {payload.get('target_type')}/{payload.get('name')} "
            f"outcome={payload.get('outcome')} agent={payload.get('agent_id')}"
        )
    if kind == "testplan.snapshot_written":
        return f"{ts}  testplan.snapshot iter={payload.get('iteration')} -> {payload.get('path')}"
    if kind == "tool.called":
        return f"{ts}    tool> {payload.get('tool_name')}({payload.get('conversation', '?')})"
    if kind == "tool.returned":
        ok = payload.get("ok")
        marker = "OK" if ok else "ERR"
        return (
            f"{ts}    tool< {payload.get('tool_name')} {marker} "
            f"({payload.get('duration_s', 0):.2f}s) {payload.get('summary', '')}"
        )
    if kind.startswith("error."):
        return f"{ts}  ERROR {payload.get('where', '')}: {payload.get('message', '')}"
    if kind.startswith("warning."):
        return f"{ts}  WARN  {payload.get('where', '')}: {payload.get('message', '')}"
    return f"{ts}  {kind}  {payload}"


class RunLogRenderer:
    def __init__(self, run_log_path: Path) -> None:
        self._path = Path(run_log_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._fh: IO[str] | None = self._path.open("a", buffering=1, encoding="utf-8")

    def render(self, event: Event) -> None:
        line = _fmt(event) + "\n"
        with self._lock:
            if self._fh is None:
                raise RuntimeError("RunLogRenderer is closed")
            self._fh.write(line)

    def close(self) -> None:
        with self._lock:
            if self._fh is not None:
                self._fh.flush()
                self._fh.close()
                self._fh = None

    def __enter__(self) -> RunLogRenderer:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


class TeeLogger:
    """Writes one event to both events.jsonl and run.log."""

    def __init__(self, events: EventLogger, run_log: RunLogRenderer) -> None:
        self._events = events
        self._run_log = run_log

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
        ev = self._events.emit(
            kind,
            payload,
            iteration=iteration,
            node=node,
            agent_id=agent_id,
            dispatch_id=dispatch_id,
        )
        self._run_log.render(ev)
        return ev

    def close(self) -> None:
        self._events.close()
        self._run_log.close()

    def __enter__(self) -> TeeLogger:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
