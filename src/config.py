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

    # Functional coverage
    functional_coverage_enabled: bool       # FUNCTIONAL_COVERAGE_ENABLED
    functional_coverage_target: float       # FUNCTIONAL_COVERAGE_TARGET (default: 100.0)
    functional_coverage_testbench_path: Optional[Path]  # FUNCTIONAL_COVERAGE_TESTBENCH

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
    coverage_hole_radius: int  # Context lines above/below each coverage hole (0-20)
    context_window: int  # Max tokens before terminating run
    keep_latest_failures: int  # Number of latest failed verification cycle pairs to keep in context

    # LangGraph
    recursion_limit: int  # LangGraph graph recursion limit

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
    uvm_home: Optional[str]               # UVM 1.2 install root
    uvm_dpi_lib: Optional[str]            # Path to UVM DPI shared library
    uvm_seq_item_file: Optional[Path]     # Path to seq_item file (for LLM context)
    uvm_coverage_module_file: Optional[Path]  # Path to passive coverage module
    # ────────────────────────────────────────────────────────────────────────

    # Multi-agent (v2 / v2.1)
    architecture: str  # "v1", "v2", or "v2.1" — selects which graph to build
    orchestrator_model: str  # Model for orchestrator agent (both v2 and v2.1)
    # v2 (expert+generator) models
    design_expert_model: str  # Model for design expert agent
    test_generator_model: str  # Model for test generator agent
    expert_context_limit: int  # Token limit before expert context is considered full
    # v2.1 (analyzer-generator+crt) models
    analyzer_generator_model: str  # Model for analyzer-generator agents
    crt_model: str  # Model for CRT (constrained random test) agents
    # Shared
    gen_max_retries: int  # Max compile/sim failures per generator dispatch
    max_gen_per_iter: int  # Max generators per orchestrator iteration

    # Debug
    log_level: str
    log_truncate: bool  # Whether to truncate long content in logs

    # Runtime tracking (mutable)
    current_iteration: int = 1
    # Auto-detected UVM names (populated at init, used by validators)
    uvm_interface_name: Optional[str] = None   # e.g., alu_core_if
    uvm_env_class: Optional[str] = None        # e.g., alu_core_env
    uvm_driver_file: Optional[Path] = None     # Auto-detected driver file path
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

    model = os.getenv("MODEL", "gpt-4o")

    # ── Functional Coverage Configuration ──────────────────────────────────
    uvm_will_be_enabled = os.getenv("UVM_ENABLED", "0") == "1"
    func_cov_enabled = os.getenv("FUNCTIONAL_COVERAGE_ENABLED", "0") == "1"
    func_cov_target = float(os.getenv("FUNCTIONAL_COVERAGE_TARGET", "100.0"))
    func_cov_tb_env = os.getenv("FUNCTIONAL_COVERAGE_TESTBENCH")
    func_cov_tb_path: Optional[Path] = None
    if func_cov_tb_env:
        func_cov_tb_path = Path(func_cov_tb_env)
    elif hasattr(design_config, 'functional_coverage_testbench_path') and design_config.functional_coverage_testbench_path:
        func_cov_tb_path = design_config.functional_coverage_testbench_path
    if func_cov_enabled and not uvm_will_be_enabled and not test_mode:
        if func_cov_tb_path is None:
            raise ValueError(
                "FUNCTIONAL_COVERAGE_ENABLED=1 requires a testbench template. "
                "Set FUNCTIONAL_COVERAGE_TESTBENCH or add 'verif' key in dashboard."
            )
        if not func_cov_tb_path.exists():
            raise ValueError(f"Functional coverage testbench not found: {func_cov_tb_path}")
    # ────────────────────────────────────────────────────────────────────────

    # ── UVM Mode Configuration ────────────────────────────────────────────
    uvm_enabled = uvm_will_be_enabled
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
        uvm_home = os.getenv("UVM_HOME", "/opt/siemens/questasim/uvm-1.2")

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

        if not uvm_filelist or not uvm_filelist.exists():
            raise ValueError(f"UVM_ENABLED=1 but filelist not found: {uvm_filelist}")
        if not uvm_sequence_file:
            raise ValueError("UVM_ENABLED=1 but UVM_SEQUENCE_FILE not set")
        if not uvm_top_module:
            raise ValueError("UVM_ENABLED=1 but UVM_TOP_MODULE not set")
        if not uvm_test_name:
            raise ValueError("UVM_ENABLED=1 but UVM_TEST_NAME not set")

        logging.info(f"UVM mode enabled: top={uvm_top_module}, test={uvm_test_name}")

        uvm_coverage_mode = os.getenv("UVM_COVERAGE_MODE", "functional").lower()
        if uvm_coverage_mode not in ("functional", "line"):
            raise ValueError(
                f"Invalid UVM_COVERAGE_MODE: '{uvm_coverage_mode}'. "
                f"Must be 'functional' or 'line'."
            )
        logging.info(f"UVM coverage mode: {uvm_coverage_mode}")

        if uvm_coverage_mode == "functional":
            func_cov_enabled = True
    # ────────────────────────────────────────────────────────────────────────

    return Config(
        openai_api_key=api_key,
        model=model,
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
        functional_coverage_enabled=func_cov_enabled,
        functional_coverage_target=func_cov_target,
        functional_coverage_testbench_path=func_cov_tb_path,
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
        coverage_hole_radius=max(0, min(20, int(os.getenv("COVERAGE_HOLE_RADIUS", "5")))),
        context_window=int(os.getenv("CONTEXT_WINDOW", "128000")),
        keep_latest_failures=int(os.getenv("KEEP_LATEST_FAILURES", "1")),
        recursion_limit=int(os.getenv("RECURSION_LIMIT", "300")),
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
        architecture=os.getenv("ARCHITECTURE", "v1").lower().replace("_", "."),
        orchestrator_model=os.getenv("ORCHESTRATOR_MODEL", model),
        design_expert_model=os.getenv("DESIGN_EXPERT_MODEL", model),
        test_generator_model=os.getenv("TEST_GENERATOR_MODEL", model),
        expert_context_limit=int(os.getenv("EXPERT_CONTEXT_LIMIT", "100000")),
        analyzer_generator_model=os.getenv("ANALYZER_GENERATOR_MODEL", os.getenv("DESIGN_EXPERT_MODEL", model)),
        crt_model=os.getenv("CRT_MODEL", os.getenv("TEST_GENERATOR_MODEL", model)),
        gen_max_retries=int(os.getenv("GEN_MAX_RETRIES", "3")),
        max_gen_per_iter=int(os.getenv("MAX_GEN_PER_ITER", "3")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_truncate=os.getenv("LOG_TRUNCATE", "1") == "1"
    )
