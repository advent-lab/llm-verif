"""Dispatch brief, generator return, and orchestrator action types."""

from __future__ import annotations

from typing import Literal, TypedDict

from pydantic import BaseModel, Field

GoalType = Literal["absolute", "delta", "bin_set", "stimulus_only"]
StopReason = Literal["goal", "budget", "plateau", "error"]
ProposedStatus = Literal["complete", "incomplete", "blocked"]


class DispatchGoal(BaseModel):
    type: GoalType
    target: dict = Field(default_factory=dict)


class DispatchBudget(BaseModel):
    max_iterations: int = 5
    max_tokens: int | None = None


class ItemContext(BaseModel):
    target_type: Literal["testpoint", "covergroup", "code_scope"]
    name: str
    description: str = ""
    history: list[dict] = Field(default_factory=list)
    instructions: str = ""
    coverage: dict | None = None


class DispatchBrief(BaseModel):
    """Orchestrator → agent hand-off. In-memory only; not persisted as a doc."""

    agent_id: str
    feature_label: str
    scope_items: list[str]
    instructions: str = ""
    rtl_context: list[str] = Field(default_factory=list)
    spec_excerpts: list[str] = Field(default_factory=list)
    baseline_coverage: dict = Field(default_factory=dict)
    goal: DispatchGoal
    budget: DispatchBudget = Field(default_factory=DispatchBudget)
    items_context: list[ItemContext] = Field(default_factory=list)


class ItemReport(BaseModel):
    name: str
    target_type: Literal["testpoint", "covergroup", "code_scope"]
    proposed_status: ProposedStatus
    summary: str = ""
    artifacts_path: str | None = None
    coverage: dict | None = None


class GeneratorReport(BaseModel):
    """Agent → orchestrator return. Recommendations only — orchestrator decides."""

    agent_id: str
    feature_label: str
    items: list[ItemReport] = Field(default_factory=list)
    issues_encountered: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    recommendations_for_next_pass: list[str] = Field(default_factory=list)
    stop_reason: StopReason


class RouteDecision(TypedDict):
    """Why the orchestrator chose to stop dispatching."""

    reason: Literal["goal_met", "budget_exhausted", "plateau", "error"]
    summary: str


class DispatchPlan(TypedDict):
    """A batch of dispatch briefs the orchestrator emits in one iteration."""

    briefs: list[DispatchBrief]


class OrchestratorAction(TypedDict):
    """Tagged union returned by the orchestrate node."""

    kind: Literal["dispatch", "terminate"]
    dispatch_plan: DispatchPlan | None
    route_decision: RouteDecision | None
