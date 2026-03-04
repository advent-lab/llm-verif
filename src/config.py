from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
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

    # Design
    design_name: str
    design_dir: Path
    spec_path: Path
    design_files: List[Path]
    design_context_files: List[Path]
    design_context_enabled: bool

    # Paths
    work_dir: Path          # Includes RUN_ID (and phase subdir in combined mode)
    simulator_path: Path    # COMPILER environment variable (path to binaries)
    simulator_type: str     # SIMULATOR environment variable ('questasim' or 'verilator')

    # Workflow
    run_id: str
    max_iterations: int
    max_retries: int
    max_no_progress: int    # Maximum consecutive cycles with no coverage improvement
    sim_runs: int
    sim_timeout: int
    testplan_enabled: bool
    num_feedback_holes: int # Number of priority coverage holes in feedback (0 = none)
    context_window: int     # Max tokens before terminating run

    # Functional Coverage
    functional_coverage_enabled: bool          # Enable functional coverage mode
    functional_coverage_target: float          # Target functional coverage percentage
    functional_coverage_testbench_path: Optional[Path]  # Path to user-provided testbench

    # ── Combined Coverage Mode ──────────────────────────────────────────────
    # When True, the framework runs code coverage first (Phase 1) then
    # automatically transitions to functional coverage (Phase 2) using the
    # same RUN_ID but separate work subdirectories:
    #   work/<RUN_ID>/code_cov/
    #   work/<RUN_ID>/func_cov/
    combined_coverage_enabled: bool
    # ────────────────────────────────────────────────────────────────────────

    # Debug
    log_level: str
    log_truncate: bool      # Whether to truncate long content in logs

    # Runtime tracking (mutable)
    current_iteration: int = 1
    current_attempt: int = 1  # Tracks all compilation/simulation attempts

    # Iteration-based retry tracking (for log naming)
    compile_attempts_this_iter: int = 0
    sim_attempts_this_iter: int = 0
    _last_iter_for_compile: int = 0
    _last_iter_for_sim: int = 0


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
        logging.info("=" * 60)
        logging.info("TEST_MODE ENABLED - Using mock simulator tools")
        logging.info("=" * 60)

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

    # Simulator configuration
    compiler = os.getenv("COMPILER", "/mock/simulator/path")
    simulator = os.getenv("SIMULATOR", "questasim").lower()

    valid_simulators = ["questasim", "verilator"]
    if simulator not in valid_simulators:
        raise ValueError(f"Invalid SIMULATOR: {simulator}. Must be one of: {valid_simulators}")

    if not test_mode:
        if not compiler or not Path(compiler).exists():
            raise ValueError(f"COMPILER path invalid: {compiler}")
        logging.info(f"Using {simulator} simulator at: {compiler}")
    else:
        logging.info(f"Test mode: Using {simulator} simulator (mocked) at: {compiler}")

    # ── Work directory ──────────────────────────────────────────────────────
    # Combined mode: work/<RUN_ID>/code_cov/   (Phase 1 starts here;
    #                                           phase_transition_node switches
    #                                           to work/<RUN_ID>/func_cov/)
    # Single mode:   work/<RUN_ID>/            (unchanged from before)
    run_id = os.getenv("RUN_ID", "default_run")
    work_base = Path(os.getenv("WORK_DIR", "./work"))

    combined_coverage_enabled = os.getenv("COMBINED_COVERAGE_ENABLED", "0") == "1"

    if combined_coverage_enabled:
        work_dir = (work_base / run_id / "code_cov").resolve()
    else:
        work_dir = (work_base / run_id).resolve()
    # ────────────────────────────────────────────────────────────────────────

    # Determine design_dir from spec_path
    design_dir = design_config.spec_path.parent.parent

    # ── Functional Coverage Configuration ──────────────────────────────────
    # In combined mode, functional_coverage_enabled starts as False (Phase 1
    # is code coverage). The phase_transition_node flips it to True for Phase 2.
    # In single functional-coverage mode it is set from the env var as before.
    if combined_coverage_enabled:
        funcov_enabled = False   # Phase 1 starts in code coverage mode
    else:
        funcov_enabled = os.getenv("FUNCTIONAL_COVERAGE_ENABLED", "0") == "1"

    funcov_target = float(os.getenv("FUNCTIONAL_COVERAGE_TARGET", "100.0"))

    funcov_testbench_path = None
    if funcov_enabled:
        # Only required when running functional coverage as a standalone mode
        funcov_tb_env = os.getenv("FUNCTIONAL_COVERAGE_TESTBENCH")
        if funcov_tb_env:
            funcov_testbench_path = Path(funcov_tb_env)
        elif hasattr(design_config, 'functional_coverage_testbench_path'):
            funcov_testbench_path = design_config.functional_coverage_testbench_path

        if funcov_testbench_path and not funcov_testbench_path.exists():
            raise FileNotFoundError(
                f"Functional coverage testbench not found: {funcov_testbench_path}"
            )

        if not funcov_testbench_path:
            raise ValueError(
                "FUNCTIONAL_COVERAGE_ENABLED=1 but no testbench provided. "
                "Set FUNCTIONAL_COVERAGE_TESTBENCH or add to dashboard.json"
            )

        logging.info(f"Functional coverage mode enabled with testbench: {funcov_testbench_path}")

    if combined_coverage_enabled:
        # Validate that FUNCTIONAL_COVERAGE_TESTBENCH is set for Phase 2,
        # even though we don't activate it yet. Fail early rather than
        # discovering the missing value only after Phase 1 completes.
        funcov_tb_env = os.getenv("FUNCTIONAL_COVERAGE_TESTBENCH")
        if funcov_tb_env:
            combined_funcov_tb = Path(funcov_tb_env)
            if not combined_funcov_tb.exists():
                raise FileNotFoundError(
                    f"FUNCTIONAL_COVERAGE_TESTBENCH not found (needed for Phase 2): {combined_funcov_tb}"
                )
        elif not (hasattr(design_config, 'functional_coverage_testbench_path') and
                  design_config.functional_coverage_testbench_path):
            raise ValueError(
                "COMBINED_COVERAGE_ENABLED=1 requires FUNCTIONAL_COVERAGE_TESTBENCH "
                "to be set (used for Phase 2 functional coverage)."
            )
        logging.info("Combined coverage mode enabled: code coverage → functional coverage")
    # ────────────────────────────────────────────────────────────────────────

    return Config(
        openai_api_key=api_key,
        model=os.getenv("MODEL", "gpt-4o"),
        temperature=float(os.getenv("TEMPERATURE", "0.4")),
        max_tokens=int(os.getenv("MAX_TOKENS", "4096")),
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
        max_iterations=int(os.getenv("MAX_ITERATIONS", "20")),
        max_retries=int(os.getenv("MAX_RETRIES", "3")),
        max_no_progress=int(os.getenv("MAX_NO_PROGRESS", "5")),
        sim_runs=int(os.getenv("SIM_RUNS", "5")),
        sim_timeout=int(os.getenv("SIM_TIMEOUT", "60")),
        testplan_enabled=os.getenv("TESTPLAN", "1") == "1",
        num_feedback_holes=int(os.getenv("NUM_FEEDBACK_HOLES", "3")),
        context_window=int(os.getenv("CONTEXT_WINDOW", "128000")),
        functional_coverage_enabled=funcov_enabled,
        functional_coverage_target=funcov_target,
        functional_coverage_testbench_path=funcov_testbench_path,
        combined_coverage_enabled=combined_coverage_enabled,
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_truncate=os.getenv("LOG_TRUNCATE", "1") == "1",
    )
