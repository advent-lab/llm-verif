"""Agent definitions for CovAgent multi-agent architectures.

v2 (orc_exp_gen.py): Orchestrator-Expert-Generator
    - design_expert: persistent Design Expert agent
    - test_generator: stateless Test Generator agents
    - orchestrator: tools for v2 orchestrator

v2.1 (ag_crt.py): Orchestrator → Analyzer-Generator + CRT
    - analyzer_generator: combines RTL analysis with testbench generation
    - crt_agent: broad constrained random test generation
    - _result_utils: shared result extraction
"""

# v2 exports
from .design_expert import create_design_expert, invoke_expert
from .test_generator import dispatch_generator, make_generator_tools

# v2.1 exports
from .analyzer_generator import dispatch_analyzer_generator, make_analyzer_generator_tools
from .crt_agent import dispatch_crt_agent, make_crt_tools
from ._result_utils import extract_agent_result

# Shared
from .orchestrator import make_orchestrator_tools
from .ag_crt_orchestrator import make_ag_crt_orchestrator_tools
