from pathlib import Path
from typing import Dict, Any, List, Tuple
from langchain.tools import tool
import logging
import os
import re

_config = None
_adapter = None  # Simulator adapter instance

def set_config(config):
    """Set config and initialize appropriate simulator adapter."""
    global _config, _adapter
    _config = config

    simulator_type = getattr(config, 'simulator_type', 'questasim').lower()

    if simulator_type == 'questasim':
        from ..simulators.questasim_adapter import QuestasimAdapter
        _adapter = QuestasimAdapter(config.simulator_path)
        logging.info("Initialized QuestaSim adapter")
    elif simulator_type == 'verilator':
        from ..simulators.verilator_adapter import VerilatorAdapter
        _adapter = VerilatorAdapter(config.simulator_path)
        logging.info("Initialized Verilator adapter")
    else:
        raise ValueError(f"Unsupported simulator type: {simulator_type}")


# ── XMR validator ──────────────────────────────────────────────────────────────

# Patterns that identify cross-module references in SystemVerilog testbenches.
# Each tuple is (pattern, human_readable_description).
#
# An XMR is any dotted hierarchical path that goes deeper than one level from
# the DUT instance (i.e. references a submodule internal signal).  We also
# catch force/release statements which almost always accompany XMRs and are
# equally forbidden.
#
# We intentionally do NOT flag:
#   - dut.<port>          — top-level DUT port connections are fine
#   - $root, $unit        — these are scope qualifiers, not hierarchy traversals
#   - module.parameter    — parameterised instantiations (no dot-chain depth >1)
#   - Comments            — lines starting with // or inside /* */
#
_XMR_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # Hierarchical path 2+ levels deep: dut.x.y  or  tb.dut.x  etc.
    # Matches any identifier sequence with 2 or more dots that is not a
    # pure numeric literal (e.g. 1.0) or a file path string.
    (
        re.compile(
            r'\b([A-Za-z_]\w*\.){2,}[A-Za-z_]\w*\b'
        ),
        "hierarchical path reference (2+ levels deep)",
    ),
    # force / release statements — these are only valid targeting XMRs
    # and are never acceptable in generated testbenches.
    (
        re.compile(r'\bforce\b\s+\S'),
        "force statement (XMR-based forcing is forbidden)",
    ),
    (
        re.compile(r'\brelease\b\s+\S'),
        "release statement (XMR-based release is forbidden)",
    ),
]

# Lines that look like XMRs but are actually fine — exempt patterns.
# If a line matches one of these it is skipped even if an XMR pattern fires.
_XMR_EXEMPTIONS: List[re.Pattern] = [
    re.compile(r'^\s*//'),           # single-line comment
    re.compile(r'^\s*\*'),           # inside block comment
    re.compile(r'`timescale'),       # timescale directive
    # DUT top-level port connection: .port_name(signal)  — not a hierarchy walk
    re.compile(r'^\s*\.[A-Za-z_]\w*\s*\('),
]


def _check_for_xmrs(tb_path: Path) -> List[str]:
    """
    Scan a testbench file for cross-module references (XMRs).

    Returns a list of human-readable violation strings, one per offending line.
    Returns an empty list if the file is clean.

    The check is line-by-line so that the error message returned to the LLM
    pinpoints exactly which lines need to be removed or rewritten.
    """
    violations: List[str] = []

    try:
        source = tb_path.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        logging.warning(f"XMR check: could not read {tb_path}: {e}")
        return violations

    lines = source.splitlines()
    inside_block_comment = False

    for lineno, raw_line in enumerate(lines, start=1):
        line = raw_line

        # Track block comments /* ... */
        if '/*' in line:
            inside_block_comment = True
        if '*/' in line:
            inside_block_comment = False
            continue
        if inside_block_comment:
            continue

        # Skip exempt lines
        if any(pat.search(line) for pat in _XMR_EXEMPTIONS):
            continue

        # Check each XMR pattern
        for pattern, description in _XMR_PATTERNS:
            m = pattern.search(line)
            if m:
                snippet = line.strip()[:120]
                violations.append(
                    f"  Line {lineno:4d}: {description}\n"
                    f"             {snippet}"
                )
                break  # one violation per line is enough

    return violations


def _build_xmr_error_message(tb_path: Path, violations: List[str]) -> str:
    """
    Build the error string returned to the LLM when XMRs are detected.

    Formatted to look like a compiler error so the LLM treats it with the
    same priority as a real QuestaSim compilation failure.
    """
    lines = [
        "** ERROR: Testbench rejected — Cross-Module References (XMRs) detected. **",
        "",
        "XMRs are STRICTLY FORBIDDEN in generated testbenches.",
        "This includes:",
        "  - Hierarchical paths deeper than the DUT top level  (e.g. dut.submodule.signal)",
        "  - force / release statements targeting internal signals",
        "  - Any reference to signals inside submodule instances",
        "",
        f"Violations found in {tb_path.name}:",
    ]
    lines.extend(violations)
    lines += [
        "",
        "HOW TO FIX — rewrite the testbench so that:",
        "  1. All stimulus is applied ONLY through the DUT top-level ports.",
        "  2. No 'force' or 'release' statements are used.",
        "  3. No dotted paths deeper than one level appear anywhere.",
        "  4. Internal FSM states are reached by driving correct port sequences,",
        "     NOT by forcing internal registers directly.",
        "",
        "Generate a new testbench that follows these rules and call compile_design again.",
    ]
    return "\n".join(lines)


# ── Tools ──────────────────────────────────────────────────────────────────────

@tool
def compile_design(testbench_path: str) -> Dict[str, Any]:
    """
    Compile the testbench with all design files.

    Supports both QuestaSim and Verilator based on configuration.
    Automatically enables functional coverage flags if FUNCTIONAL_COVERAGE_ENABLED=1.

    Args:
        testbench_path: Path to testbench file (relative to work directory)

    Returns:
        Dictionary with success, return_code, stdout, stderr, log_path

    The compiler automatically includes all RTL files from the design directory.
    Coverage instrumentation:
    - Code coverage mode: Statement coverage (QuestaSim) or line coverage (Verilator)
    - Functional coverage mode: Full coverage including functional bins (+cover=sbfec)
    """
    try:
        # Get current iteration for naming
        iteration = _config.current_iteration

        # Reset compile attempt counter if iteration changed
        if _config._last_iter_for_compile != iteration:
            _config.compile_attempts_this_iter = 0
            _config._last_iter_for_compile = iteration

        # Increment compile attempt for this iteration
        _config.compile_attempts_this_iter += 1
        retry_num = _config.compile_attempts_this_iter

        # Resolve testbench path
        tb_path = (_config.work_dir / testbench_path).resolve()
        if not tb_path.exists():
            return {
                "success": False,
                "error": f"Testbench not found: {testbench_path}",
                "iteration": iteration,
                "retry": retry_num,
            }

        # ── XMR pre-check ──────────────────────────────────────────────────
        # Reject the testbench immediately if any cross-module references are
        # found.  This fires BEFORE QuestaSim is invoked so no compile slot is
        # wasted and the error message is clear and actionable.
        xmr_violations = _check_for_xmrs(tb_path)
        if xmr_violations:
            error_msg = _build_xmr_error_message(tb_path, xmr_violations)
            logging.warning(
                f"XMR pre-check FAILED for {tb_path.name}: "
                f"{len(xmr_violations)} violation(s) found"
            )

            # Write rejection to a log file so it is auditable
            log_name = (
                f"compile_iter_{iteration}.log"
                if retry_num == 1
                else f"compile_iter_{iteration}_retry_{retry_num}.log"
            )
            log_path = _config.work_dir / "logs" / log_name
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, 'w') as f:
                f.write(f"=== XMR PRE-CHECK FAILED: Iteration {iteration}, "
                        f"Attempt {retry_num} ===\n")
                f.write(f"Testbench: {testbench_path}\n\n")
                f.write(error_msg)

            return {
                "success": False,
                "return_code": 1,
                "stdout": error_msg,
                "stderr": "",
                "log_path": str(log_path),
                "iteration": iteration,
                "retry": retry_num,
            }
        # ── End XMR pre-check ──────────────────────────────────────────────

        # Get design files from config
        design_files = _config.design_files + _config.design_context_files

        # Delegate to adapter
        result = _adapter.compile(
            testbench_path=tb_path,
            design_files=design_files,
            work_dir=_config.work_dir,
            timeout=_config.sim_timeout
        )

        # Build log filename
        if retry_num == 1:
            log_name = f"compile_iter_{iteration}.log"
        else:
            log_name = f"compile_iter_{iteration}_retry_{retry_num}.log"

        log_path = _config.work_dir / "logs" / log_name
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, 'w') as f:
            f.write(f"=== COMPILATION: Iteration {iteration}, Attempt {retry_num} ===\n")
            f.write(f"Testbench: {testbench_path}\n")
            f.write(f"Success: {result.get('success', False)}\n")
            f.write(f"Return Code: {result.get('return_code', 'N/A')}\n\n")
            f.write(f"STDOUT:\n{result.get('stdout', '(empty)')}\n\n")
            f.write(f"STDERR:\n{result.get('stderr', '(empty)')}\n")
        result["log_path"] = str(log_path)

        # Summarize output for the LLM
        if result.get("success", False):
            result["stdout"] = f"Compilation successful. Full log: {log_name}"
            result.pop("stderr", None)
        else:
            stderr = result.get("stderr", "")
            stdout = result.get("stdout", "")
            error_output = stderr or stdout or "Unknown error"
            result["error_summary"] = (
                f"Compilation failed. Check {log_name} for details.\n"
                f"{error_output[:500]}"
            )
            result["stdout"] = _adapter.filter_compile_output(result.get("stdout", ""))
            result["stderr"] = _adapter.filter_compile_output(result.get("stderr", ""))

        result["iteration"] = iteration
        result["retry"] = retry_num
        return result

    except Exception as e:
        logging.error(f"Compilation error: {e}")
        return {"success": False, "error": str(e)}


@tool
def run_simulation(testbench_name: str = "tb_llm", num_runs: int = None) -> Dict[str, Any]:
    """
    Run simulation with coverage collection.

    Supports both QuestaSim and Verilator based on configuration.
    In functional coverage mode, automatically generates a text coverage report.

    Args:
        testbench_name: Name of testbench module (default: "tb_llm")
        num_runs: Number of simulation runs with different random seeds (default: from config)

    Returns:
        Dictionary with success, stdout, stderr, coverage_db_path, log_path
        If functional coverage mode: Also includes functional_coverage_report_path

    Multiple runs help achieve better random coverage.
    For QuestaSim: Coverage databases are automatically merged.
    For Verilator: Coverage accumulates to a single .dat file.

    FUNCTIONAL COVERAGE MODE:
    If FUNCTIONAL_COVERAGE_ENABLED=1, this tool also generates a text-based
    functional coverage report using vcover report -details.
    """
    try:
        if num_runs is None:
            num_runs = _config.sim_runs

        iteration = _config.current_iteration

        if _config._last_iter_for_sim != iteration:
            _config.sim_attempts_this_iter = 0
            _config._last_iter_for_sim = iteration

        _config.sim_attempts_this_iter += 1
        retry_num = _config.sim_attempts_this_iter

        result = _adapter.simulate(
            testbench_name=testbench_name,
            num_runs=num_runs,
            work_dir=_config.work_dir,
            iteration=iteration,
            timeout=_config.sim_timeout
        )

        if retry_num == 1:
            log_name = f"sim_iter_{iteration}.log"
        else:
            log_name = f"sim_iter_{iteration}_retry_{retry_num}.log"

        log_path = _config.work_dir / "logs" / log_name
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, 'w') as f:
            f.write(f"=== SIMULATION: Iteration {iteration}, Attempt {retry_num} ===\n")
            f.write(f"Testbench: {testbench_name}\n")
            f.write(f"Num Runs: {num_runs}\n")
            f.write(f"Success: {result.get('success', False)}\n\n")
            f.write(f"STDOUT:\n{result.get('stdout', '(empty)')}\n")
            if result.get("stderr"):
                f.write(f"\nSTDERR:\n{result.get('stderr', '(empty)')}\n")
        result["log_path"] = str(log_path)

        funcov_enabled = getattr(_config, 'functional_coverage_enabled', False)
        if funcov_enabled and result.get("success", False):
            ucdb_path = Path(result.get("coverage_db_path"))
            if ucdb_path and ucdb_path.exists():
                funcov_report_path = _generate_functional_coverage_report(
                    ucdb_path, iteration
                )
                if funcov_report_path:
                    result["functional_coverage_report_path"] = str(funcov_report_path)
                    logging.info(f"Generated functional coverage report: {funcov_report_path}")

        if result.get("success", False):
            result["stdout"] = (
                f"Simulation completed: "
                f"{result.get('num_runs_completed', num_runs)}/{num_runs} "
                f"runs successful. Full log: {log_name}"
            )
            result.pop("stderr", None)
        else:
            error_msg = result.get("error", "")
            stderr = result.get("stderr", "")
            stdout = result.get("stdout", "")
            error_output = error_msg or stderr or stdout or "Unknown error"
            result["error_summary"] = (
                f"Simulation failed. Check {log_name} for details.\n"
                f"{error_output[:500]}"
            )
            result["stdout"] = _adapter.filter_sim_output(result.get("stdout", ""))
            result["stderr"] = _adapter.filter_sim_output(result.get("stderr", ""))

        result["iteration"] = iteration
        result["retry"] = retry_num
        return result

    except Exception as e:
        logging.error(f"Simulation error: {e}")
        return {"success": False, "error": str(e)}


def _generate_functional_coverage_report(ucdb_path: Path, iteration: int) -> Path:
    """Generate text-based functional coverage report."""
    try:
        from ..simulators.questasim_adapter import generate_functional_coverage_report

        coverage_dir = ucdb_path.parent
        report_path = coverage_dir / f"functional_coverage_iter_{iteration}.txt"

        success = generate_functional_coverage_report(
            simulator_path=_config.simulator_path,
            ucdb_path=ucdb_path,
            output_txt=report_path
        )

        if success:
            return report_path
        else:
            logging.error("Functional coverage report generation failed")
            return None

    except Exception as e:
        logging.error(f"Error generating functional coverage report: {e}")
        return None
