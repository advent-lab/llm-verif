"""Orchestrator (top-level) state — long-lived across iterations."""

from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from covagent.config import RunConfig
from covagent.state.agent import CoverageSnapshot
from covagent.state.dispatch import DispatchBrief, GeneratorReport
from covagent.state.testplan import Testplan

RunStatus = Literal["init", "running", "blocked", "done", "errored"]
AgentStatus = Literal["active", "idle", "retired"]


class AgentMetadata(TypedDict):
    agent_id: str
    feature_label: str
    scope_items: list[str]
    work_dir: str
    status: AgentStatus
    spawned_at: str
    last_invoked_at: str | None
    invocation_count: int


class DispatchRecord(TypedDict):
    dispatch_id: str
    iteration: int
    feature: str
    item_names: list[str]
    agent_id: str
    brief_summary: str
    return_summary: str
    work_dir: str
    timestamp: str


class GeneratorHandle(TypedDict):
    agent_id: str
    dispatch_id: str
    brief: DispatchBrief


class GeneratorReturn(TypedDict):
    agent_id: str
    dispatch_id: str
    report: GeneratorReport


class FeaturePlan(TypedDict):
    feature_label: str
    item_names: list[str]
    rationale: str


class CycleScratch(TypedDict):
    candidate_features: list[FeaturePlan]
    in_flight: list[GeneratorHandle]
    pending_results: list[GeneratorReturn]
    coverage_snapshot: CoverageSnapshot | None


def dict_merge(left: dict, right: dict) -> dict:
    """Reducer: shallow-merge two dicts (right wins on conflict)."""
    return {**left, **right}


def replace(_left: object, right: object) -> object:
    """Reducer: take the right value verbatim."""
    return right


def list_concat(left: list, right: list) -> list:
    """Reducer: concatenate two lists (existing + new entries)."""
    return list(left) + list(right)


def dispatch_log_concat(
    left: list, right: list
) -> list:
    """Reducer for `dispatch_log`: concatenate, deduping by dispatch_id.

    Defensive against LangGraph internal replay calling the reducer multiple
    times with overlapping entries — keeps the audit trail unique while still
    accumulating across iterations.
    """
    out = list(left)
    seen = {entry.get("dispatch_id") for entry in out if isinstance(entry, dict)}
    for entry in right:
        did = entry.get("dispatch_id") if isinstance(entry, dict) else None
        if did is not None and did in seen:
            continue
        out.append(entry)
        if did is not None:
            seen.add(did)
    return out


class OrchestratorState(TypedDict):
    config: RunConfig
    run_id: str

    design_digest: str | None

    testplan: Testplan
    dispatch_log: Annotated[list[DispatchRecord], dispatch_log_concat]
    agents: Annotated[dict[str, AgentMetadata], dict_merge]

    iteration: int
    run_status: RunStatus

    messages: Annotated[list[AnyMessage], add_messages]

    cycle: CycleScratch
