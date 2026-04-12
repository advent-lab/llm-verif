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
    reasoning_effort: str  # 'disabled', 'none', 'low', 'medium', or 'high'

    # Design
    design_name: str
    design_dir: Path
    spec_path: Path
    design_files: List[Path]
    design_context_files: List[Path]
    compile_deps_files: List[Path]
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
    max_no_tool_calls: int  # Maximum consecutive agent responses with no tool calls
    sim_runs: int
    sim_timeout: int
    testplan_enabled: bool
    num_feedback_holes: int  # Priority coverage holes in feedback (0 = unbounded)
    coverage_hole_radius: int  # Context lines above/below each coverage hole (0-20)
    context_window: int      # Max tokens before terminating run
    read_file_token_limit: int  # Max chars returned by read_file (0 = unlimited)
    keep_latest_failures: int  # Number of latest failed verification cycle pairs to keep in context

    # LangGraph
    recursion_limit: int  # LangGraph graph recursion limit

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

    # ── UVM Mode ──────────────────────────────────────────────────────────
    # When True, compilation uses UVM 3-step flow (vlib → vlog → vopt),
    # simulation uses optimized design with UVM flags, and the LLM generates
    # UVM sequence + test files instead of complete testbenches.
    uvm_enabled: bool
    uvm_coverage_mode: str                # "functional" (default) or "line"
    uvm_testbench_dir: Optional[Path]     # Dir containing UVM TB components
    uvm_filelist: Optional[Path]          # .f file listing all UVM sources
    uvm_sequence_file: Optional[str]      # Filename of sequence file to generate
    uvm_top_module: Optional[str]         # Top-level module name (e.g., alu_core_Top)
    uvm_test_name: Optional[str]          # UVM test class name (e.g., alu_core_test)
    uvm_home: Optional[str]               # UVM 1.2 install root (e.g. /opt/siemens/questasim/uvm-1.2)
    uvm_dpi_lib: Optional[str]            # Path to UVM DPI shared library
    uvm_seq_item_file: Optional[Path]     # Path to seq_item file (for LLM context)
    uvm_coverage_module_file: Optional[Path]  # Path to passive coverage module
    # ────────────────────────────────────────────────────────────────────────

    # Debug
    log_level: str
    log_truncate: bool      # Whether to truncate long content in logs

    # Runtime tracking (mutable)
    current_iteration: int = 1
    # Auto-detected UVM names (populated at init, used by validators)
    uvm_interface_name: Optional[str] = None   # e.g., alu_core_if
    uvm_env_class: Optional[str] = None        # e.g., alu_core_env
    uvm_driver_file: Optional[Path] = None    # Auto-detected driver file path
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

    # Validate reasoning effort
    reasoning_effort = os.getenv("REASONING_EFFORT", "disabled").lower()
    # valid_reasoning = ["disabled", "none", "minimal", "low", "medium", "high", "xhigh"]
    # if reasoning_effort not in valid_reasoning:
    #     raise ValueError(f"Invalid REASONING_EFFORT: {reasoning_effort}. Must be one of: {valid_reasoning}")

    # Determine design_dir from spec_path (spec is always in docs/ under design root)
    # spec_path.parent = docs/, spec_path.parent.parent = design root
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
    # UVM mode handles functional coverage via passive coverage module;
    # skip the testbench template requirement.
    uvm_will_be_enabled = os.getenv("UVM_ENABLED", "0") == "1"
    if funcov_enabled and not uvm_will_be_enabled:
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

    # ── UVM Mode Configuration ────────────────────────────────────────────
    uvm_enabled = os.getenv("UVM_ENABLED", "0") == "1"
    uvm_coverage_mode = "functional"  # Default; overridden below if UVM enabled
    uvm_testbench_dir = None
    uvm_filelist = None
    uvm_sequence_file = None
    uvm_top_module = None
    uvm_test_name = None
    uvm_dpi_lib = None
    uvm_seq_item_file = None
    uvm_coverage_module_file = None

    uvm_home = None

    if uvm_enabled:
        # UVM_HOME: root of the UVM 1.2 installation
        uvm_home = os.getenv("UVM_HOME", "/opt/siemens/questasim/uvm-1.2")

        # Pull from design_config (dashboard) or env vars
        uvm_testbench_dir = getattr(design_config, 'uvm_testbench_dir', None)
        if not uvm_testbench_dir:
            env_val = os.getenv("UVM_TESTBENCH_DIR")
            uvm_testbench_dir = Path(env_val) if env_val else None

        uvm_filelist = getattr(design_config, 'uvm_filelist', None)
        if not uvm_filelist:
            env_val = os.getenv("UVM_FILELIST")
            uvm_filelist = Path(env_val) if env_val else None

        uvm_sequence_file = getattr(design_config, 'uvm_sequence_file', None) or \
                            os.getenv("UVM_SEQUENCE_FILE")

        uvm_top_module = getattr(design_config, 'uvm_top_module', None) or \
                         os.getenv("UVM_TOP_MODULE")

        uvm_test_name = getattr(design_config, 'uvm_test_name', None) or \
                        os.getenv("UVM_TEST_NAME")

        uvm_dpi_lib = os.getenv(
            "UVM_DPI_LIB",
            "/opt/siemens/questasim/uvm-1.2/linux_x86_64/uvm_dpi"
        )

        uvm_seq_item_file = getattr(design_config, 'uvm_seq_item_file', None)
        if not uvm_seq_item_file:
            env_val = os.getenv("UVM_SEQ_ITEM_FILE")
            uvm_seq_item_file = Path(env_val) if env_val else None

        uvm_coverage_module_file = getattr(design_config, 'uvm_coverage_module_file', None)
        if not uvm_coverage_module_file:
            env_val = os.getenv("UVM_COVERAGE_MODULE_FILE")
            uvm_coverage_module_file = Path(env_val) if env_val else None

        # Validate required UVM fields
        if not uvm_filelist or not uvm_filelist.exists():
            raise ValueError(f"UVM_ENABLED=1 but filelist not found: {uvm_filelist}")
        if not uvm_sequence_file:
            raise ValueError("UVM_ENABLED=1 but UVM_SEQUENCE_FILE not set")
        if not uvm_top_module:
            raise ValueError("UVM_ENABLED=1 but UVM_TOP_MODULE not set")
        if not uvm_test_name:
            raise ValueError("UVM_ENABLED=1 but UVM_TEST_NAME not set")

        logging.info(f"UVM mode enabled: top={uvm_top_module}, test={uvm_test_name}")

        # UVM_COVERAGE_MODE: "functional" (default) or "line"
        #   "functional" — targets both code + functional coverage (original behavior)
        #   "line"       — targets line/statement coverage only via parse_coverage
        uvm_coverage_mode = os.getenv("UVM_COVERAGE_MODE", "functional").lower()
        if uvm_coverage_mode not in ("functional", "line"):
            raise ValueError(
                f"Invalid UVM_COVERAGE_MODE: '{uvm_coverage_mode}'. "
                f"Must be 'functional' or 'line'."
            )
        logging.info(f"UVM coverage mode: {uvm_coverage_mode}")

        # In "functional" mode, force funcov_enabled so coverage parsing handles both.
        # In "line" mode, leave funcov_enabled as-is (False) — the pipeline iterates
        # on statement/line coverage only.
        if uvm_coverage_mode == "functional":
            funcov_enabled = True
    # ────────────────────────────────────────────────────────────────────────

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
        compile_deps_files=design_config.compile_deps_files,
        design_context_enabled=os.getenv("DESIGN_CONTEXT", "1") == "1",
        work_dir=work_dir,
        simulator_path=Path(compiler),
        simulator_type=simulator,
        run_id=run_id,
        max_iterations=int(os.getenv("MAX_ITERATIONS", "20")),
        max_retries=int(os.getenv("MAX_RETRIES", "3")),
        max_no_progress=int(os.getenv("MAX_NO_PROGRESS", "5")),
        max_no_tool_calls=int(os.getenv("MAX_NO_TOOL_CALLS", "3")),
        sim_runs=int(os.getenv("SIM_RUNS", "5")),
        sim_timeout=int(os.getenv("SIM_TIMEOUT", "60")),
        testplan_enabled=os.getenv("TESTPLAN", "1") == "1",
        num_feedback_holes=int(os.getenv("NUM_FEEDBACK_HOLES", "0")),
        coverage_hole_radius=max(0, min(20, int(os.getenv("COVERAGE_HOLE_RADIUS", "5")))),
        context_window=int(os.getenv("CONTEXT_WINDOW", "128000")),
        keep_latest_failures=int(os.getenv("KEEP_LATEST_FAILURES", "1")),
        recursion_limit=int(os.getenv("RECURSION_LIMIT", "300")),
        read_file_token_limit=int(os.getenv("READ_FILE_TOKEN_LIMIT", "16000")),
        functional_coverage_enabled=funcov_enabled,
        functional_coverage_target=funcov_target,
        functional_coverage_testbench_path=funcov_testbench_path,
        combined_coverage_enabled=combined_coverage_enabled,
        uvm_enabled=uvm_enabled,
        uvm_coverage_mode=uvm_coverage_mode,
        uvm_home=uvm_home,
        uvm_testbench_dir=uvm_testbench_dir,
        uvm_filelist=uvm_filelist,
        uvm_sequence_file=uvm_sequence_file,
        uvm_top_module=uvm_top_module,
        uvm_test_name=uvm_test_name,
        uvm_dpi_lib=uvm_dpi_lib,
        uvm_seq_item_file=uvm_seq_item_file,
        uvm_coverage_module_file=uvm_coverage_module_file,
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_truncate=os.getenv("LOG_TRUNCATE", "1") == "1",
    )
