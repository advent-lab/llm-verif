"""Simulator adapters for different HDL simulators.

This package provides a unified interface for different HDL simulators through
the adapter pattern. Each simulator (QuestaSim, Verilator, etc.) implements
the SimulatorAdapter interface.

Available adapters:
- QuestasimAdapter: Mentor Graphics QuestaSim commercial simulator
- VerilatorAdapter: Verilator open-source compile-to-C++ simulator

Usage:
    from simulators.questasim_adapter import QuestasimAdapter
    adapter = QuestasimAdapter(simulator_path)
    result = adapter.compile(testbench, design_files, work_dir, timeout)
"""

from .base import SimulatorAdapter, CoverageResult
from .questasim_adapter import QuestasimAdapter
from .verilator_adapter import VerilatorAdapter

__all__ = [
    'SimulatorAdapter',
    'CoverageResult',
    'QuestasimAdapter',
    'VerilatorAdapter'
]
