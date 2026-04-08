from pathlib import Path
from typing import Dict, Any, Optional, List
from langchain.tools import tool
import logging
import re

_config = None
_adapter = None  # Simulator adapter instance
_cumulative_coverage_db: Optional[Path] = None  # Path to cumulative coverage database

def set_config(config):
    """Set config and initialize appropriate simulator adapter.

    This is called after simulation.set_config(), so the adapter should
    be the same type. We reinitialize it here for the analysis module.
    """
    global _config, _adapter
    _config = config

    # Factory pattern: select adapter based on config
    simulator_type = getattr(config, 'simulator_type', 'questasim').lower()

    if simulator_type == 'questasim':
        from ..simulators.questasim_adapter import QuestasimAdapter
        _adapter = QuestasimAdapter(config.simulator_path)
    elif simulator_type == 'verilator':
        from ..simulators.verilator_adapter import VerilatorAdapter
        _adapter = VerilatorAdapter(config.simulator_path)
    else:
        raise ValueError(f"Unsupported simulator type: {simulator_type}")

def set_cumulative_coverage_db(path: Optional[Path]):
    """Set the path to the cumulative coverage database."""
    global _cumulative_coverage_db
    _cumulative_coverage_db = path

def get_cumulative_coverage_db() -> Optional[Path]:
    """Get the path to the cumulative coverage database."""
    return _cumulative_coverage_db

@tool
def parse_coverage(coverage_db_path: str) -> Dict[str, Any]:
    """
    Parse coverage database and extract detailed metrics.

    Supports both QuestaSim (.ucdb) and Verilator (.dat) formats.
    Automatically merges with cumulative coverage across all iterations.

    Args:
        coverage_db_path: Path to coverage database
            - QuestaSim: .ucdb file
            - Verilator: .dat file

    Returns:
        Dictionary with:
        - success: bool
        - iteration_coverage: float (0-100) - this testbench alone
        - cumulative_coverage: float (0-100) - all testbenches combined
        - total_coverage: float (same as cumulative_coverage, for backward compatibility)
        - breakdown: dict (module/file name -> coverage percentage) - from cumulative
        - uncovered_lines: dict (file_path -> list of line numbers) - from cumulative
        - annotated_source: str (source code with coverage markers) - from cumulative
        - cumulative_coverage_db: str - path to merged cumulative database
        - error: str (if failed)

    The annotated_source shows lines NOT YET covered by ANY testbench:
    - "   N |" = Line executed N times (covered by some testbench)
    - "##### |" = Line NOT executed by any testbench (TARGET THIS)
    - "    - |" = Non-coverable line (declarations, comments)
    """
    global _cumulative_coverage_db

    try:
        db_path = Path(coverage_db_path).resolve()
        if not db_path.exists():
            return {"success": False, "error": f"Coverage database not found: {coverage_db_path}"}

        # Step 1: Parse iteration coverage (this testbench alone)
        logging.info("Parsing iteration coverage database")
        iteration_result = _adapter.parse_coverage(db_path)
        iteration_coverage = iteration_result.total_coverage
        logging.info(f"Iteration coverage: {iteration_coverage:.1f}%")

        # Step 2: Determine cumulative coverage database path
        coverage_dir = db_path.parent
        simulator_type = getattr(_config, 'simulator_type', 'questasim').lower()
        if simulator_type == 'questasim':
            cumulative_db_path = coverage_dir / "cumulative.ucdb"
        else:
            cumulative_db_path = coverage_dir / "cumulative.dat"

        # Step 3: Merge iteration coverage into cumulative
        try:
            _adapter.merge_cumulative_coverage(db_path, cumulative_db_path)
            _cumulative_coverage_db = cumulative_db_path
        except Exception as e:
            logging.error(f"Cumulative merge failed: {e}")
            # Fall back to just using iteration coverage
            _cumulative_coverage_db = db_path
            cumulative_db_path = db_path

        # Step 4: Parse cumulative coverage (all testbenches combined)
        logging.info("Parsing cumulative coverage database")
        cumulative_result = _adapter.parse_coverage(cumulative_db_path)
        cumulative_coverage = cumulative_result.total_coverage
        logging.info(f"Cumulative coverage: {cumulative_coverage:.1f}%")

        # Step 5: Create annotated source based on CUMULATIVE uncovered lines
        # (what still needs to be covered by future testbenches)
        max_holes = getattr(_config, 'num_feedback_holes', 3) if _config else 3
        annotated_source = _create_annotated_source(cumulative_result.uncovered_lines, max_holes)

        return {
            "success": True,
            "iteration_coverage": iteration_coverage,
            "cumulative_coverage": cumulative_coverage,
            "total_coverage": cumulative_coverage,  # Backward compatibility
            "breakdown": cumulative_result.breakdown,
            "uncovered_lines": cumulative_result.uncovered_lines,
            "annotated_source": annotated_source,
            "cumulative_coverage_db": str(cumulative_db_path)
        }

    except FileNotFoundError as e:
        logging.error(f"Coverage database not found: {e}")
        return {"success": False, "error": str(e)}
    except RuntimeError as e:
        logging.error(f"Coverage parsing failed: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logging.error(f"Coverage parsing error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return {"success": False, "error": str(e)}

@tool
def parse_functional_coverage(coverage_db_path: str) -> Dict[str, Any]:
    """
    Parse functional coverage database and generate feedback for uncovered bins.

    This tool is used in FUNCTIONAL COVERAGE MODE to analyze which coverage bins
    have not been hit and provide actionable feedback to guide stimulus generation.

    Args:
        coverage_db_path: Path to coverage database (.ucdb for QuestaSim)
            This is the per-iteration coverage database that will be merged
            with cumulative coverage from all previous iterations.

    Returns:
        Dictionary with:
        - success: bool
        - total_coverage: float (0-100) - Overall cumulative functional coverage
        - iteration_coverage: float (0-100) - This iteration alone (for debugging)
        - cumulative_coverage: float (0-100) - Same as total_coverage
        - covergroups: list of covergroup details with uncovered bins (from cumulative)
        - feedback: str (human-readable guidance for the LLM)
        - uncovered_bins: list of all uncovered bins with full context (from cumulative)
            Each entry: {covergroup, instance_path, coverpoint, coverpoint_kind,
                         bin_name, covergroup_coverage, sample_event}
        - cumulative_coverage_db: str - path to merged cumulative database
        - error: str (if failed)
    """
    global _cumulative_coverage_db

    try:
        from ..utils.questasim import parse_functional_coverage_text

        db_path = Path(coverage_db_path).resolve()
        if not db_path.exists():
            return {
                "success": False,
                "error": f"Coverage database not found: {coverage_db_path}"
            }

        # Step 1: Determine cumulative coverage database path
        coverage_dir = db_path.parent
        cumulative_db_path = coverage_dir / "cumulative_funcov.ucdb"

        # Step 2: Merge this iteration's coverage into cumulative
        logging.info(f"Merging functional coverage: {db_path} → {cumulative_db_path}")
        try:
            _adapter.merge_cumulative_coverage(db_path, cumulative_db_path)
            _cumulative_coverage_db = cumulative_db_path
        except Exception as e:
            logging.error(f"Cumulative functional coverage merge failed: {e}")
            _cumulative_coverage_db = db_path
            cumulative_db_path = db_path

        # Step 3: Generate functional coverage report from CUMULATIVE database
        logging.info("Generating functional coverage report from cumulative database")
        report_path = coverage_dir / "cumulative_functional_coverage.txt"

        import subprocess
        vcover_cmd = [
            str(_adapter.simulator_path / "vcover"),
            "report",
            "-details",
            "-output", str(report_path),
            str(cumulative_db_path)
        ]

        try:
            subprocess.run(vcover_cmd, check=True, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            logging.error("vcover report generation timed out")
            return {"success": False, "error": "Coverage report generation timed out"}
        except subprocess.CalledProcessError as e:
            logging.error(f"vcover report failed: {e.stderr}")
            return {"success": False, "error": f"Coverage report generation failed: {e.stderr}"}

        # Step 4: Parse the cumulative report
        logging.info(f"Parsing cumulative functional coverage report: {report_path}")
        result = parse_functional_coverage_text(report_path)

        if 'error' in result:
            return {"success": False, "error": result['error']}

        cumulative_coverage = result['total_coverage']
        covergroups = result['covergroups']

        # Generate enriched human-readable feedback for the LLM
        feedback = _generate_functional_coverage_feedback(cumulative_coverage, covergroups)

        # ── Build enriched flat uncovered_bins list ────────────────────────
        # Each entry now carries the full hierarchy context so the orchestrator
        # and analyzer always know exactly where each uncovered bin sits and
        # what conditions trigger sampling.
        all_uncovered_bins = []
        for cg in covergroups:
            for bin_entry in cg.get('uncovered_bins', []):
                if isinstance(bin_entry, dict):
                    # New enriched format from updated parse_functional_coverage_text
                    all_uncovered_bins.append({
                        'covergroup':          cg['name'],
                        'instance_path':       cg.get('instance_path', ''),
                        'coverpoint':          bin_entry.get('coverpoint', ''),
                        'coverpoint_kind':     bin_entry.get('coverpoint_kind', 'Coverpoint'),
                        'bin_name':            bin_entry.get('bin_name', bin_entry),
                        'covergroup_coverage': cg.get('coverage', 0.0),
                        'sample_event':        cg.get('sample_event', None),
                    })
                else:
                    # Fallback: old string format (should not occur after questasim.py update)
                    all_uncovered_bins.append({
                        'covergroup':          cg['name'],
                        'instance_path':       cg.get('instance_path', ''),
                        'coverpoint':          '',
                        'coverpoint_kind':     'Coverpoint',
                        'bin_name':            bin_entry,
                        'covergroup_coverage': cg.get('coverage', 0.0),
                        'sample_event':        cg.get('sample_event', None),
                    })

        logging.info(
            f"Functional coverage: {cumulative_coverage:.1f}% "
            f"({len(all_uncovered_bins)} bins uncovered)"
        )

        return {
            "success": True,
            "total_coverage": cumulative_coverage,
            "iteration_coverage": cumulative_coverage,
            "cumulative_coverage": cumulative_coverage,
            "covergroups": covergroups,
            "feedback": feedback,
            "uncovered_bins": all_uncovered_bins,
            "cumulative_coverage_db": str(cumulative_db_path)
        }

    except Exception as e:
        logging.error(f"Functional coverage parsing error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return {"success": False, "error": str(e)}


def _generate_functional_coverage_feedback(
    total_coverage: float,
    covergroups: List[Dict]
) -> str:
    """
    Generate enriched human-readable feedback about uncovered bins.

    Each uncovered bin is reported with its full context:
      - Covergroup name and instance path
      - When/how the covergroup is sampled (sample_event)
      - Coverpoint or cross name and kind
      - Bin name

    This gives the LLM everything it needs to understand not just WHAT is
    uncovered but WHY it may be hard to hit — the sampling trigger is
    especially important for designs where coverage only fires on specific
    clock edges or signal transitions.

    Args:
        total_coverage: Total functional coverage percentage
        covergroups: List of covergroup dicts from parse_functional_coverage_text

    Returns:
        Formatted feedback string for the LLM
    """
    if total_coverage >= 99.9:
        return "✓ Functional coverage complete! All bins have been hit."

    feedback = [f"## Functional Coverage: {total_coverage:.1f}%\n"]

    # Find covergroups with uncovered bins
    incomplete_cgs = [cg for cg in covergroups if cg.get('uncovered_bins')]

    if not incomplete_cgs:
        return "✓ All bins covered (or no functional coverage defined)."

    # Count total uncovered bins across all covergroups
    total_uncovered = sum(len(cg['uncovered_bins']) for cg in incomplete_cgs)
    feedback.append(
        f"### Uncovered Bins ({total_uncovered} bins across "
        f"{len(incomplete_cgs)} covergroup(s))\n"
    )

    # Show details for up to 5 covergroups
    for cg in incomplete_cgs[:5]:
        cg_name       = cg['name']
        cg_path       = cg.get('instance_path', cg_name)
        cg_coverage   = cg.get('coverage', 0.0)
        sample_event  = cg.get('sample_event')
        uncovered     = cg.get('uncovered_bins', [])

        # ── Covergroup header ──────────────────────────────────────────────
        feedback.append(f"**Covergroup: `{cg_name}`** ({cg_coverage:.1f}% covered)")
        feedback.append(f"  Instance: `{cg_path}`")

        if sample_event:
            feedback.append(
                f"  Sampled: `{sample_event}`  "
                f"← coverage is only recorded when this event fires"
            )
        else:
            feedback.append(
                "  Sampled: implicit (called via .sample() in testbench)"
            )

        feedback.append(f"  Missing {len(uncovered)} bin(s):")
        feedback.append("")

        # Group bins by coverpoint so the output is scannable
        by_coverpoint: Dict[str, List] = {}
        for bin_entry in uncovered:
            if isinstance(bin_entry, dict):
                cp_key  = bin_entry.get('coverpoint', '(unknown)')
                cp_kind = bin_entry.get('coverpoint_kind', 'Coverpoint')
                bin_name = bin_entry.get('bin_name', str(bin_entry))
            else:
                cp_key   = '(unknown)'
                cp_kind  = 'Coverpoint'
                bin_name = str(bin_entry)

            if cp_key not in by_coverpoint:
                by_coverpoint[cp_key] = {'kind': cp_kind, 'bins': []}
            by_coverpoint[cp_key]['bins'].append(bin_name)

        # Print up to 10 total bins, grouped by coverpoint
        bins_shown = 0
        for cp_name, cp_data in by_coverpoint.items():
            if bins_shown >= 10:
                break
            cp_kind = cp_data['kind']
            feedback.append(f"  {cp_kind}: `{cp_name}`")
            for bin_name in cp_data['bins']:
                if bins_shown >= 10:
                    break
                feedback.append(f"    - `{bin_name}`")
                bins_shown += 1

        remaining = len(uncovered) - bins_shown
        if remaining > 0:
            feedback.append(f"    ... and {remaining} more bin(s)")

        feedback.append("")

    if len(incomplete_cgs) > 5:
        feedback.append(
            f"  _(and {len(incomplete_cgs) - 5} more covergroup(s) with uncovered bins)_\n"
        )

    # Actionable guidance
    feedback.append("### What to do next:")
    feedback.append(
        "1. **Check the sample event** — if coverage uses `@(posedge clk)`, "
        "your stimulus must allow the clock to tick with the right signal values "
        "present BEFORE the edge fires."
    )
    feedback.append(
        "2. **Target the coverpoint** — understand what signal/expression each "
        "coverpoint measures, then drive that signal to the bin's required value."
    )
    feedback.append(
        "3. **Target the bin** — use the bin name to infer what value or "
        "condition is needed (e.g. `neg_one` → set operand to -1, "
        "`invalid[8]` → set opcode to 4'h8)."
    )
    feedback.append(
        "4. **Focus on lowest coverage first** — covergroups with lowest "
        "coverage percentage have the most bins still to hit."
    )

    return "\n".join(feedback)


def _create_annotated_source(uncovered_lines: Dict[str, list], max_holes: int = 3) -> str:
    """Create annotated source highlighting high-priority uncovered lines.

    Args:
        uncovered_lines: Mapping of file paths to lists of uncovered line numbers.
        max_holes: Number of priority holes to include. 0 disables output.

    Returns:
        Combined annotated snippets separated by hole headers, or empty string
        if max_holes is 0.
    """
    if max_holes == 0:
        return ""

    if not uncovered_lines:
        return "All lines covered!"

    # Prioritize control flow statements
    prioritized = []
    for file_path, lines in uncovered_lines.items():
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                file_lines = f.readlines()

            for line_num in lines:
                if 1 <= line_num <= len(file_lines):
                    code = file_lines[line_num - 1].strip()

                    # Prioritize control flow (if, case, while, for)
                    if re.search(r'\b(if|case|while|for)\s*\(', code):
                        prioritized.insert(0, (file_path, line_num, code))
                    else:
                        prioritized.append((file_path, line_num, code))
        except:
            continue

    if not prioritized:
        return "Uncovered lines found but could not read source"

    # Select top N holes, deduplicating by proximity to avoid overlapping snippets.
    context_radius = 5
    selected = []
    for candidate in prioritized:
        if len(selected) >= max_holes:
            break
        c_file, c_line, _ = candidate
        overlaps = False
        for s_file, s_line, _ in selected:
            if c_file == s_file and abs(c_line - s_line) <= context_radius * 2:
                overlaps = True
                break
        if not overlaps:
            selected.append(candidate)

    # Build snippets for each selected hole
    snippets = []
    total = len(selected)
    for idx, (file_path, line_num, code) in enumerate(selected, 1):
        header = f"--- Hole {idx}/{total}: {Path(file_path).name}:{line_num} ---"
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                file_lines = f.readlines()

            file_lines[line_num - 1] = (
                file_lines[line_num - 1].rstrip('\n')
                + "\t// ##### UNCOVERED - TARGET THIS LINE #####\n"
            )

            start = max(0, line_num - context_radius - 1)
            end = min(len(file_lines), line_num + context_radius)
            context = ''.join(file_lines[start:end])

            snippets.append(f"{header}\n{context}")
        except:
            snippets.append(f"{header}\nUncovered line: {file_path}:{line_num} - {code}")

    return "\n\n".join(snippets)
