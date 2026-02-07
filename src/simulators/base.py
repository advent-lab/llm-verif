"""Base adapter interface for HDL simulators.

This module defines the abstract interface that all simulator adapters must implement.
The adapter pattern allows the LangGraph framework to support multiple simulators
(QuestaSim, Verilator, etc.) without changing the tool layer or agent logic.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from pathlib import Path
from dataclasses import dataclass


@dataclass
class CoverageResult:
    """Unified coverage result structure across all simulators.

    This normalizes the different coverage formats from various simulators:
    - QuestaSim: Module-based coverage (DU - Design Units)
    - Verilator: File-based coverage (FileCoverage)

    Attributes:
        total_coverage: Overall coverage percentage (0-100)
        breakdown: Module or file-level coverage breakdown {name: percentage}
        uncovered_lines: Mapping of file paths to lists of uncovered line numbers
    """
    total_coverage: float
    breakdown: Dict[str, float]
    uncovered_lines: Dict[str, List[int]]


class SimulatorAdapter(ABC):
    """Abstract base class for simulator-specific implementations.

    Each simulator (QuestaSim, Verilator, etc.) implements this interface to provide
    compilation, simulation, and coverage parsing capabilities. The adapter pattern
    ensures that tools remain simulator-agnostic while delegating implementation
    details to specific adapters.

    Attributes:
        simulator_path: Path to simulator binaries directory
    """

    def __init__(self, simulator_path: Path):
        """Initialize simulator adapter.

        Args:
            simulator_path: Path to directory containing simulator executables
        """
        self.simulator_path = Path(simulator_path)

    @abstractmethod
    def compile(self, testbench_path: Path, design_files: List[Path],
                work_dir: Path, timeout: int) -> Dict[str, Any]:
        """Compile testbench and design files.

        Args:
            testbench_path: Path to testbench SystemVerilog file
            design_files: List of design RTL files to compile
            work_dir: Working directory for compilation artifacts
            timeout: Compilation timeout in seconds

        Returns:
            Dictionary with:
                - success (bool): Compilation succeeded
                - stdout (str): Standard output from compiler
                - stderr (str): Standard error from compiler
                - log_path (str): Path to saved compilation log
                - return_code (int, optional): Process return code
                - error (str, optional): Error message if failed
        """
        pass

    @abstractmethod
    def simulate(self, testbench_name: str, num_runs: int,
                 work_dir: Path, iteration: int, timeout: int) -> Dict[str, Any]:
        """Run simulation with coverage collection.

        Args:
            testbench_name: Name of testbench module (e.g., "tb_llm")
            num_runs: Number of simulation runs with different random seeds
            work_dir: Working directory for simulation artifacts
            iteration: Current iteration number for file naming
            timeout: Simulation timeout in seconds per run

        Returns:
            Dictionary with:
                - success (bool): Simulation succeeded
                - stdout (str, optional): Standard output from simulation
                - stderr (str, optional): Standard error from simulation
                - coverage_db_path (str): Path to coverage database
                - log_path (str, optional): Path to saved simulation log
                - num_runs_completed (int): Number of runs that completed successfully
                - error (str, optional): Error message if failed
        """
        pass

    @abstractmethod
    def parse_coverage(self, coverage_db_path: Path) -> CoverageResult:
        """Parse coverage database and return structured results.

        Args:
            coverage_db_path: Path to coverage database file
                - QuestaSim: .ucdb file
                - Verilator: .dat file

        Returns:
            CoverageResult object with normalized coverage data

        Raises:
            FileNotFoundError: If coverage database doesn't exist
            RuntimeError: If coverage parsing fails
        """
        pass

    def filter_sim_output(self, output: str) -> str:
        """Filter simulator output to remove boilerplate noise.

        Override in subclasses to strip simulator-specific banners, loading
        messages, and other lines that waste LLM input tokens.  The default
        implementation returns the output unchanged.

        Args:
            output: Raw stdout or stderr from the simulator

        Returns:
            Filtered output string
        """
        return output

    @staticmethod
    @abstractmethod
    def cleanup(work_dir: Path) -> None:
        """Clean up simulator-specific temporary files.

        Args:
            work_dir: Working directory containing artifacts to clean
        """
        pass
