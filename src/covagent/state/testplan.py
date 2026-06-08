"""Testplan schema — owned by the orchestrator, patched via tools."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ItemStatus = Literal["todo", "incomplete", "complete", "blocked"]
HistoryOutcome = Literal["passed", "failed", "partial", "errored"]
TargetType = Literal["testpoint", "covergroup", "code_scope"]


class HistoryEntry(BaseModel):
    timestamp: str
    agent_id: str
    outcome: HistoryOutcome
    summary: str
    artifacts_path: str | None = None


class Waiver(BaseModel):
    reason: str
    approver: str
    date: str


class CoverageBlock(BaseModel):
    pct: float = 0.0
    items_hit: int = 0
    items_total: int = 0
    unhit_items: list[str] = Field(default_factory=list)
    snapshot_at: str | None = None
    target_pct: float | None = None


class _ItemBase(BaseModel):
    name: str
    description: str = ""
    steps: list[str] = Field(default_factory=list)
    status: ItemStatus = "todo"
    history: list[HistoryEntry] = Field(default_factory=list)
    # Assigned at first dispatch and immutable thereafter.
    owner_agent_id: str | None = None
    waiver: Waiver | None = None


class Testpoint(_ItemBase):
    pass


class Coverpoint(BaseModel):
    name: str
    description: str = ""
    bins: list[Bin] = Field(default_factory=list)


class Bin(BaseModel):
    name: str
    description: str = ""
    hit: bool = False


class Covergroup(_ItemBase):
    coverpoints: list[Coverpoint] = Field(default_factory=list)
    coverage: CoverageBlock = Field(default_factory=CoverageBlock)


class CodeScope(_ItemBase):
    path: str
    coverage: CoverageBlock = Field(default_factory=CoverageBlock)


class CoverageTarget(BaseModel):
    functional: float | None = None
    line: float | None = None
    toggle: float | None = None
    branch: float | None = None
    fsm: float | None = None


class Testplan(BaseModel):
    mode: Literal["functional", "code"]
    testpoints: list[Testpoint] = Field(default_factory=list)
    covergroups: list[Covergroup] = Field(default_factory=list)
    code_scopes: list[CodeScope] = Field(default_factory=list)
    coverage_target: CoverageTarget = Field(default_factory=CoverageTarget)


Coverpoint.model_rebuild()
