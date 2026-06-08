"""Verilator adapter — placeholder.

A faithful port of legacy_src/simulators/verilator_adapter.py is pending.
See questa.py for the same rationale.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from covagent.simulators.base import (
    CompileResult,
    CoverageSummary,
    MergeResult,
    RunResult,
    SimulatorAdapter,
)

_PORT_TODO = (
    "VerilatorAdapter is not yet ported from legacy_src/simulators/verilator_adapter.py. "
    "Use MockAdapter for tests/dev or port the legacy logic into this module."
)


class VerilatorAdapter(SimulatorAdapter):
    name = "verilator"

    def extension(self) -> str:
        return ".dat"

    def compile(self, *args: object, **kwargs: object) -> CompileResult:
        raise NotImplementedError(_PORT_TODO)

    def run(self, *args: object, **kwargs: object) -> RunResult:
        raise NotImplementedError(_PORT_TODO)

    def merge_coverage(
        self, master: Path, deltas: list[Path], output: Path
    ) -> MergeResult:
        raise NotImplementedError(_PORT_TODO)

    def parse_coverage(
        self, db: Path, mode: Literal["functional", "code"]
    ) -> CoverageSummary:
        raise NotImplementedError(_PORT_TODO)
