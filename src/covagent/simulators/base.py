"""SimulatorAdapter ABC and shared result types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class CompileResult(BaseModel):
    ok: bool
    error: str | None = None
    duration_s: float = 0.0
    log_path: Path | None = None
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0


class RunResult(BaseModel):
    ok: bool
    error: str | None = None
    duration_s: float = 0.0
    coverage_db: Path | None = None
    log_path: Path | None = None
    runs_completed: int = 0
    stdout: str = ""
    stderr: str = ""


class MergeResult(BaseModel):
    ok: bool
    error: str | None = None
    duration_s: float = 0.0
    output: Path | None = None


class CoverageSummary(BaseModel):
    """Structured coverage numbers — never LLM-parsed report text."""

    overall_pct: float = 0.0
    items_hit: int = 0
    items_total: int = 0
    breakdown: dict[str, float] = Field(default_factory=dict)
    unhit_items: list[str] = Field(default_factory=list)
    raw: dict = Field(default_factory=dict)


class SimulatorAdapter(ABC):
    """Adapter contract — all simulator-specific logic lives behind this."""

    name: str

    @abstractmethod
    def extension(self) -> str:
        """Coverage DB file extension, e.g. '.ucdb' or '.dat'."""

    @abstractmethod
    def compile(
        self,
        sources: list[Path],
        work_dir: Path,
        *,
        top: str | None = None,
        timeout_s: int = 300,
        compile_deps: list[Path] | None = None,
    ) -> CompileResult: ...

    @abstractmethod
    def run(
        self,
        work_dir: Path,
        *,
        test_name: str | None = None,
        coverage_db: Path | None = None,
        num_runs: int = 1,
        timeout_s: int = 600,
    ) -> RunResult: ...

    @abstractmethod
    def merge_coverage(
        self, master: Path, deltas: list[Path], output: Path
    ) -> MergeResult: ...

    @abstractmethod
    def parse_coverage(
        self, db: Path, mode: Literal["functional", "code"]
    ) -> CoverageSummary: ...
