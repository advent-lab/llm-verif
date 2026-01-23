"""Mock coverage analysis for testing without QuestaSim.

This module provides mock implementation of parse_coverage() that simulates
realistic coverage progression without requiring actual QuestaSim tools.
"""

from pathlib import Path
from typing import Dict, Any
from langchain.tools import tool
import logging
import random
import re

_config = None

def set_config(config):
    """Set global config for tools."""
    global _config
    _config = config


@tool
def parse_coverage(coverage_db_path: str) -> Dict[str, Any]:
    """
    MOCK: Simulate coverage parsing.

    Reads iteration number from UCDB path and returns progressively
    better coverage to simulate realistic agent behavior.

    Args:
        coverage_db_path: Path to UCDB file (created by mock simulation)

    Returns:
        Dict with success status, total_coverage, module_breakdown,
        uncovered_lines, and annotated_source
    """
    try:
        ucdb_path = Path(coverage_db_path)
        if not ucdb_path.exists():
            return {
                "success": False,
                "error": f"Coverage database not found: {coverage_db_path}"
            }

        # Extract iteration from path (e.g., iter_1.ucdb)
        match = re.search(r'iter_(\d+)', ucdb_path.name)
        iteration = int(match.group(1)) if match else 1

        # Simulate progressive coverage improvement
        # Iteration 1: 50-60%
        # Iteration 2-4: 60-90%
        # Iteration 5+: 90-100%
        if iteration == 1:
            coverage = random.randint(50, 60)
        elif iteration < 5:
            coverage = min(60 + (iteration * 10), 90)
        else:
            coverage = min(90 + (iteration * 2), 100)

        # Add some randomness to make it realistic
        coverage = min(coverage + random.randint(-5, 5), 100)
        coverage = max(coverage, 0)

        # Simulate uncovered lines (decrease over iterations)
        num_uncovered = max(10 - (iteration * 2), 0)
        uncovered_lines = {}

        if num_uncovered > 0:
            # Find RTL files from design directory
            rtl_dir = _config.design_dir / "rtl"
            if rtl_dir.exists():
                rtl_files = list(rtl_dir.glob("*.v")) + list(rtl_dir.glob("*.sv"))
                if rtl_files:
                    # Pick first RTL file for mock uncovered lines
                    rtl_file = str(rtl_files[0])
                    # Generate mock uncovered line numbers
                    uncovered_lines[rtl_file] = list(range(42, 42 + num_uncovered))

        # Create annotated source showing uncovered lines
        if uncovered_lines:
            # Get first file and its lines
            file_path = list(uncovered_lines.keys())[0]
            lines = uncovered_lines[file_path][:3]  # Show first 3 lines
            lines_str = ", ".join(str(l) for l in lines)

            annotated_source = f"""Priority uncovered lines in {Path(file_path).name}

  40 |   always @(posedge clk) begin
  41 |     if (rst) begin
  42 |       state <= IDLE;  // ##### UNCOVERED - TARGET THIS LINE #####
  43 |     end else begin
  44 |       state <= next_state;
  45 |     end
  46 |   end

MOCK: {num_uncovered} total uncovered lines at lines {lines_str}...

COVERAGE ANALYSIS:
- Current coverage: {coverage}%
- Target: 95%
- Gap: {max(95 - coverage, 0)}%

RECOMMENDATION:
Focus testbench on exercising the reset condition and state transitions
to cover lines {lines_str}.
"""
        else:
            annotated_source = f"""All lines covered!

COVERAGE ANALYSIS:
- Current coverage: {coverage}%
- Target: 95%
- Status: {'COMPLETE' if coverage >= 95 else 'IN PROGRESS'}

MOCK: No uncovered lines remaining.
"""

        # Calculate module breakdown (simplified for mock)
        module_breakdown = {
            "total": float(coverage),
            "design_module": float(coverage)
        }

        logging.info(f"MOCK: Coverage {coverage}% for iteration {iteration} ({num_uncovered} uncovered lines)")

        return {
            "success": True,
            "total_coverage": float(coverage),
            "module_breakdown": module_breakdown,
            "uncovered_lines": uncovered_lines,
            "annotated_source": annotated_source
        }

    except Exception as e:
        logging.error(f"Mock coverage parsing error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
