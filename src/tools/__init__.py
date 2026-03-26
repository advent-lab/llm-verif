"""Tool registry for Spec2Cov ReAct agent."""
import os

# Check if in test mode
TEST_MODE = os.getenv("TEST_MODE", "0") == "1"

# Always import filesystem and workflow tools (no simulator dependency)
from .filesystem import read_file, write_file, list_directory
from .workflow import signal_done

# Always import the analyzer tool (no simulator dependency)
from .analyzer import invoke_analyzer

# Conditionally import simulation/analysis tools
if TEST_MODE:
    from .simulation_mock import compile_design, run_simulation
    from .analysis_mock import parse_coverage
    from . import simulation_mock as simulation
    from . import analysis_mock as analysis
else:
    from .simulation import compile_design, run_simulation
    from .analysis import parse_coverage, parse_functional_coverage
    from . import simulation
    from . import analysis

# Import filesystem and analyzer modules for config
from . import filesystem
from . import analyzer


def get_all_tools():
    """Get all tools for the agent."""
    tools = [
        read_file,
        write_file,
        list_directory,
        compile_design,
        run_simulation,
        parse_coverage,
        signal_done,
        invoke_analyzer,
    ]

    # Add functional coverage tool if not in test mode
    if not TEST_MODE:
        tools.append(parse_functional_coverage)

    return tools


def set_tool_config(config):
    """Set config for all tools that need it."""
    filesystem.set_config(config)
    simulation.set_config(config)
    analysis.set_config(config)
    analyzer.set_config(config)
