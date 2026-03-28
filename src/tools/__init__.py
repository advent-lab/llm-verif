"""Tool registry for Spec2Cov ReAct agent."""

import os

# Check if in test mode
TEST_MODE = os.getenv("TEST_MODE", "0") == "1"

# Always import filesystem tools (no simulator dependency)
from .filesystem import read_file, write_file, list_directory

# Conditionally import simulation/analysis tools
if TEST_MODE:
    from .simulation_mock import compile_design, run_simulation
    from .analysis_mock import parse_coverage
    from . import simulation_mock as simulation
    from . import analysis_mock as analysis
else:
    from .simulation import compile_design, run_simulation
    from .analysis import parse_coverage
    from . import simulation
    from . import analysis

# Import filesystem and workflow modules for config
from . import filesystem
from .workflow import run_verification_cycle
from . import workflow

def get_all_tools():
    """Get all tools for the agent."""
    return [
        read_file,
        write_file,
        list_directory,
        compile_design,
        run_simulation,
        parse_coverage,
        run_verification_cycle,
    ]

def set_tool_config(config):
    """Set config for all tools that need it."""
    filesystem.set_config(config)
    simulation.set_config(config)
    analysis.set_config(config)
    workflow.set_config(config)
