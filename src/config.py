from dataclasses import dataclass, field
from pathlib import Path
from typing import List
import os
import logging
from dotenv import load_dotenv

@dataclass
class Config:
    # LLM
    openai_api_key: str
    model: str
    temperature: float
    max_tokens: int
    reasoning_effort: str  # 'disabled', 'none', 'low', 'medium', or 'high'

    # Design
    design_name: str
    design_dir: Path
    spec_path: Path
    design_files: List[Path]
    design_context_files: List[Path]
    design_context_enabled: bool

    # Paths
    work_dir: Path  # Includes RUN_ID
    simulator_path: Path  # COMPILER environment variable (path to binaries)
    simulator_type: str  # SIMULATOR environment variable ('questasim' or 'verilator')

    # Workflow
    run_id: str
    max_iterations: int
    max_retries: int
    max_no_progress: int  # Maximum consecutive cycles with no coverage improvement
    max_no_tool_calls: int  # Maximum consecutive agent responses with no tool calls
    sim_runs: int
    sim_timeout: int
    testplan_enabled: bool
    num_feedback_holes: int  # Priority coverage holes in feedback (0 = unbounded)
    coverage_hole_radius: int  # Context lines above/below each coverage hole (1-20)
    context_window: int  # Max tokens before terminating run

    # LangGraph
    recursion_limit: int  # LangGraph graph recursion limit

    # Debug
    log_level: str
    log_truncate: bool  # Whether to truncate long content in logs

    # Runtime tracking (mutable)
    current_iteration: int = 1
    current_attempt: int = 1  # Tracks all compilation/simulation attempts (always increments)

    # Iteration-based retry tracking (for log naming)
    # These reset when current_iteration changes
    compile_attempts_this_iter: int = 0
    sim_attempts_this_iter: int = 0
    _last_iter_for_compile: int = 0  # Track when to reset compile counter
    _last_iter_for_sim: int = 0  # Track when to reset sim counter

def load_config() -> Config:
    """Load configuration from .env file with validation.

    Supports two modes:
    1. Dashboard mode: DESIGN_NAME + DASHBOARD_PATH (recommended)
    2. Direct mode: DESIGN path (fallback with auto-discovery)

    Returns:
        Config object with all settings validated

    Raises:
        ValueError: If configuration is invalid or required fields missing
        FileNotFoundError: If design files or dashboard not found
    """
    load_dotenv()

    # Check if in test mode
    test_mode = os.getenv("TEST_MODE", "0") == "1"

    if test_mode:
        logging.basicConfig(level=logging.INFO)
        logging.info("="*60)
        logging.info("TEST_MODE ENABLED - Using mock simulator tools")
        logging.info("="*60)

    # Required fields (except in test mode)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key and not test_mode:
        raise ValueError("OPENAI_API_KEY not set")

    # Design loading: Dashboard mode vs Direct mode
    design_name_env = os.getenv("DESIGN_NAME")
    dashboard_path_env = os.getenv("DASHBOARD_PATH")
    design_path_env = os.getenv("DESIGN")

    design_config = None

    # Priority 1: Dashboard mode (DESIGN_NAME + DASHBOARD_PATH)
    if design_name_env and dashboard_path_env:
        from .utils.dashboard_loader import get_design_from_dashboard

        dashboard_path = Path(dashboard_path_env)
        base_dir_env = os.getenv("BASE_DIR")
        base_dir = Path(base_dir_env) if base_dir_env else None

        logging.info(f"Loading design from dashboard: {design_name_env}")

        design_config = get_design_from_dashboard(
            dashboard_path=dashboard_path,
            design_name=design_name_env,
            base_dir=base_dir
        )

    # Priority 2: Direct mode (DESIGN path with auto-discovery)
    elif design_path_env:
        from .utils.dashboard_loader import auto_discover_design

        design_dir = Path(design_path_env)
        if not design_dir.exists():
            raise ValueError(f"DESIGN path does not exist: {design_dir}")

        logging.info(f"Auto-discovering design files in: {design_dir}")

        design_config = auto_discover_design(design_dir)

    else:
        raise ValueError(
            "Design configuration missing. Please set either:\n"
            "  1. DESIGN_NAME + DASHBOARD_PATH (recommended), or\n"
            "  2. DESIGN (for ad-hoc designs)"
        )

    # Simulator configuration (matches legacy framework naming)
    # COMPILER = path to simulator binaries (e.g., /scratch/vpatel69/verilator/bin)
    # SIMULATOR = simulator type ('questasim' or 'verilator')
    compiler = os.getenv("COMPILER", "/mock/simulator/path")
    simulator = os.getenv("SIMULATOR", "questasim").lower()

    # Validate simulator type
    valid_simulators = ["questasim", "verilator"]
    if simulator not in valid_simulators:
        raise ValueError(f"Invalid SIMULATOR: {simulator}. Must be one of: {valid_simulators}")

    # Compiler path validation - skip in test mode
    if not test_mode:
        if not compiler or not Path(compiler).exists():
            raise ValueError(f"COMPILER path invalid: {compiler}")
        logging.info(f"Using {simulator} simulator at: {compiler}")
    else:
        logging.info(f"Test mode: Using {simulator} simulator (mocked) at: {compiler}")

    # Build work directory with RUN_ID
    run_id = os.getenv("RUN_ID", "default_run")
    work_base = Path(os.getenv("WORK_DIR", "./work"))
    work_dir = (work_base / run_id).resolve()

    # Validate reasoning effort
    reasoning_effort = os.getenv("REASONING_EFFORT", "disabled").lower()
    # valid_reasoning = ["disabled", "none", "minimal", "low", "medium", "high", "xhigh"]
    # if reasoning_effort not in valid_reasoning:
    #     raise ValueError(f"Invalid REASONING_EFFORT: {reasoning_effort}. Must be one of: {valid_reasoning}")

    # Determine design_dir from spec_path (spec is always in docs/ under design root)
    # spec_path.parent = docs/, spec_path.parent.parent = design root
    design_dir = design_config.spec_path.parent.parent

    return Config(
        openai_api_key=api_key,
        model=os.getenv("MODEL", "gpt-4o"),
        temperature=float(os.getenv("TEMPERATURE", "0.4")),
        max_tokens=int(os.getenv("MAX_TOKENS", "4096")),
        reasoning_effort=reasoning_effort,
        design_name=design_config.design_name,
        design_dir=design_dir,
        spec_path=design_config.spec_path,
        design_files=design_config.design_files,
        design_context_files=design_config.design_context_files,
        design_context_enabled=os.getenv("DESIGN_CONTEXT", "1") == "1",
        work_dir=work_dir,
        simulator_path=Path(compiler),
        simulator_type=simulator,
        run_id=run_id,
        max_iterations=int(os.getenv("MAX_ITERATIONS", "10")),
        max_retries=int(os.getenv("MAX_RETRIES", "3")),
        max_no_progress=int(os.getenv("MAX_NO_PROGRESS", "5")),
        max_no_tool_calls=int(os.getenv("MAX_NO_TOOL_CALLS", "3")),
        sim_runs=int(os.getenv("SIM_RUNS", "5")),
        sim_timeout=int(os.getenv("SIM_TIMEOUT", "60")),
        testplan_enabled=os.getenv("TESTPLAN", "1") == "1",
        num_feedback_holes=int(os.getenv("NUM_FEEDBACK_HOLES", "0")),
        coverage_hole_radius=max(1, min(20, int(os.getenv("COVERAGE_HOLE_RADIUS", "5")))),
        context_window=int(os.getenv("CONTEXT_WINDOW", "128000")),
        recursion_limit=int(os.getenv("RECURSION_LIMIT", "300")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_truncate=os.getenv("LOG_TRUNCATE", "1") == "1"
    )
