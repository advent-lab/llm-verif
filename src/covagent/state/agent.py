"""Agent (generator) state — persistent across dispatches, keyed by agent_id."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from covagent.state.dispatch import (
    DispatchBrief,
    GeneratorReport,
    ProposedStatus,
    StopReason,
)


class CoverageSnapshot(TypedDict):
    """Structured coverage observation. Authority is the simulator DB."""

    timestamp: str
    scope: str
    pct: float
    items_hit: int
    items_total: int
    detail: dict


class AgentState(TypedDict):
    agent_id: str
    feature_label: str
    scope_items: list[str]
    work_dir: str

    current_brief: DispatchBrief | None

    attempt: int
    stop_reason: StopReason | None

    messages: Annotated[list[AnyMessage], add_messages]

    coverage_baseline: CoverageSnapshot
    coverage_history: Annotated[list[CoverageSnapshot], operator.add]

    proposed_status: dict[str, ProposedStatus]
    report: GeneratorReport | None
