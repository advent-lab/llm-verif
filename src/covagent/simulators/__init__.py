"""Simulator adapter registry."""

from __future__ import annotations

from pathlib import Path

from covagent.simulators.base import (
    CompileResult,
    CoverageSummary,
    MergeResult,
    RunResult,
    SimulatorAdapter,
)
from covagent.simulators.mock import MockAdapter
from covagent.simulators.questa import QuestaAdapter
from covagent.simulators.verilator import VerilatorAdapter

REGISTRY: dict[str, type[SimulatorAdapter]] = {
    "mock": MockAdapter,
    "questa": QuestaAdapter,
    "verilator": VerilatorAdapter,
}


def get_adapter(name: str, *, sim_path: Path | None = None) -> SimulatorAdapter:
    if name not in REGISTRY:
        raise KeyError(f"unknown simulator '{name}'; have {sorted(REGISTRY)}")
    cls = REGISTRY[name]
    if name == "questa":
        return QuestaAdapter(sim_path=sim_path)
    return cls()


__all__ = [
    "CompileResult",
    "CoverageSummary",
    "MergeResult",
    "REGISTRY",
    "RunResult",
    "SimulatorAdapter",
    "MockAdapter",
    "QuestaAdapter",
    "VerilatorAdapter",
    "get_adapter",
]
