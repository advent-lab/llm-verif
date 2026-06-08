"""Run configuration — frozen snapshot per CovAgent invocation.

`RunConfig` is instantiated by the CLI from flags / a config file, then
serialized to `<run>/config.json` at run start. After freeze it is read-only
for the duration of the run. There are NO environment-variable knobs in the
new framework (that pattern from legacy is intentionally dropped).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

CoverageMode = Literal["functional", "code"]
SimulatorName = Literal["questa", "verilator", "mock"]


class CoverageGoal(BaseModel):
    """Coverage target the orchestrator pursues."""

    overall_pct: float = Field(ge=0.0, le=100.0, default=90.0)
    per_scope_pct: float | None = Field(default=None, ge=0.0, le=100.0)


class Budget(BaseModel):
    """Hard ceilings on the run."""

    max_iterations: int = Field(default=20, ge=1)
    max_dispatches: int = Field(default=100, ge=1)
    max_wall_time_s: int = Field(default=24 * 3600, ge=1)
    per_dispatch_attempts: int = Field(default=5, ge=1)


class ModelConfig(BaseModel):
    """LLM selection per role."""

    orchestrator: str = "claude-opus-4-7"
    agent: str = "claude-sonnet-4-6"
    init: str = "claude-sonnet-4-6"
    temperature: float = 0.0


class RunConfig(BaseModel):
    """Frozen run configuration.

    Serialized verbatim to <run>/config.json. Mutating after freeze is a bug.
    """

    model_config = {"frozen": True}

    workspace: Path
    design_name: str
    dashboard_path: Path

    mode: CoverageMode = "functional"
    simulator: SimulatorName = "questa"

    goal: CoverageGoal = Field(default_factory=CoverageGoal)
    budget: Budget = Field(default_factory=Budget)
    models: ModelConfig = Field(default_factory=ModelConfig)

    @field_validator("workspace", "dashboard_path")
    @classmethod
    def _expand(cls, v: Path) -> Path:
        return Path(v).expanduser().resolve()
