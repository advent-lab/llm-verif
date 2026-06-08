"""Shared tool types — ToolResult and ToolContext."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, TypedDict

from covagent.simulators.base import SimulatorAdapter
from covagent.state.testplan import Testplan

ConversationKind = Literal["init", "orchestrate", "agent"]


class ToolResult(TypedDict, total=False):
    """Uniform tool return shape — LLMs read `summary`, code reads `data`."""

    ok: bool
    data: Any
    error: str | None
    summary: str


@dataclass
class ToolContext:
    """Per-call runtime context for tool execution.

    Each graph node constructs its own ToolContext with the subset of
    capabilities its tools need. Fields not used by a tool may be left default.
    """

    # Identity
    run_id: str
    conversation: ConversationKind
    iteration: int | None = None
    node: str | None = None
    agent_id: str | None = None
    dispatch_id: str | None = None

    # Filesystem roots
    sandbox_root: Path | None = None
    # Single read sandbox: every design file (RTL, spec, context) is reachable
    # under this directory by dashboard convention. Tools join relative paths
    # to design_root and reject anything that escapes it.
    design_root: Path | None = None
    work_dir: Path | None = None

    # Coverage / sim
    simulator: SimulatorAdapter | None = None
    coverage_master: Path | None = None
    coverage_mode: Literal["functional", "code"] = "functional"

    # State holders (single-item lists used as mutable refs)
    testplan_ref: list[Testplan] = field(default_factory=list)
    agents_ref: list[dict] = field(default_factory=list)
    dispatch_log_ref: list[list] = field(default_factory=list)

    # Logging
    emit: Callable[..., Any] | None = None

    # Design file list (resolved absolute paths from DesignEntry.design + design_context).
    # run_sim prepends these to the compile sources so agents never need to name DUT files.
    design_files: list[Path] = field(default_factory=list)

    # Limits
    max_read_bytes: int = 64_000
    unhit_truncate: int = 50
