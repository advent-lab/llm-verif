from pathlib import Path
from typing import Dict, Any, List, Optional
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
        logging.info(f"Iteration coverage: {iteration_coverage:.2f}%")

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
        logging.info(f"Cumulative coverage: {cumulative_coverage:.2f}%")

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
            # "uncovered_lines": cumulative_result.uncovered_lines, (optional) unnecessary tokens
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

    Merges the iteration UCDB into a cumulative functional coverage database
    (cumulative_funcov.ucdb), then generates and parses a vcover text report
    to extract covergroup/coverpoint/bin-level data.

    Args:
        coverage_db_path: Path to coverage database (.ucdb)

    Returns:
        Dictionary with:
        - success: bool
        - total_coverage: float (cumulative functional coverage %)
        - cumulative_coverage: float (same as total_coverage)
        - covergroups: list of covergroup dicts with uncovered_bins
        - feedback: formatted string summarising what to target next
        - uncovered_bins: flat list of all uncovered bin descriptors
        - cumulative_coverage_db: str path to merged functional UCDB
        - error: str (only on failure)
    """
    global _cumulative_coverage_db

    try:
        db_path = Path(coverage_db_path).resolve()
        if not db_path.exists():
            return {"success": False, "error": f"Coverage database not found: {coverage_db_path}"}

        coverage_dir = db_path.parent
        cumulative_db_path = coverage_dir / "cumulative_funcov.ucdb"

        logging.info(f"Merging functional coverage: {db_path} → {cumulative_db_path}")
        try:
            _adapter.merge_cumulative_coverage(db_path, cumulative_db_path)
            _cumulative_coverage_db = cumulative_db_path
        except Exception as e:
            logging.error(f"Cumulative functional coverage merge failed: {e}")
            _cumulative_coverage_db = db_path
            cumulative_db_path = db_path

        logging.info("Parsing functional coverage from cumulative database")
        result = _adapter.parse_functional_coverage(cumulative_db_path)

        if 'error' in result:
            return {"success": False, "error": result['error']}

        cumulative_coverage = result['total_coverage']
        covergroups = result['covergroups']

        feedback = _generate_functional_coverage_feedback(cumulative_coverage, covergroups)

        # Flatten uncovered bins with enriched fields
        all_uncovered_bins = []
        for cg in covergroups:
            for bin_entry in cg.get('uncovered_bins', []):
                if isinstance(bin_entry, dict):
                    all_uncovered_bins.append({
                        'covergroup':          cg['name'],
                        'instance_path':       cg.get('instance_path', ''),
                        'coverpoint':          bin_entry.get('coverpoint', ''),
                        'coverpoint_kind':     bin_entry.get('coverpoint_kind', 'Coverpoint'),
                        'bin_name':            bin_entry.get('bin_name', ''),
                        'covergroup_coverage': cg.get('coverage', 0.0),
                        'sample_event':        cg.get('sample_event'),
                    })
                else:
                    all_uncovered_bins.append({
                        'covergroup': cg['name'],
                        'bin_name':   bin_entry,
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
    """Generate human-readable feedback about uncovered bins for the LLM."""
    if total_coverage >= 99.9:
        return "Functional coverage complete! All bins have been hit."

    feedback = [f"## Functional Coverage: {total_coverage:.1f}%\n"]

    incomplete_cgs = [cg for cg in covergroups if cg.get('uncovered_bins')]
    if not incomplete_cgs:
        return "All bins covered (or no functional coverage defined)."

    total_uncovered = sum(len(cg['uncovered_bins']) for cg in incomplete_cgs)
    feedback.append(
        f"### Uncovered Bins ({total_uncovered} bins across "
        f"{len(incomplete_cgs)} covergroup(s))\n"
    )

    for cg in incomplete_cgs:
        cg_name       = cg['name']
        instance_path = cg.get('instance_path', '')
        cg_coverage   = cg.get('coverage', 0.0)
        sample_event  = cg.get('sample_event')
        uncovered     = cg.get('uncovered_bins', [])

        feedback.append(f"**Covergroup: `{cg_name}`** ({cg_coverage:.1f}% covered)")
        if instance_path:
            feedback.append(f"  Instance: `{instance_path}`")
        if sample_event:
            feedback.append(
                f"  Sampled: `{sample_event}`  "
                f"*(coverage is only recorded when this event fires)*"
            )
        else:
            feedback.append("  Sampled: implicit (called via .sample() in testbench)")

        feedback.append(f"  Missing {len(uncovered)} bin(s):\n")

        by_coverpoint: Dict[str, Dict] = {}
        for entry in uncovered:
            if isinstance(entry, dict):
                cp_key  = entry.get('coverpoint', 'unknown')
                cp_kind = entry.get('coverpoint_kind', 'Coverpoint')
                bin_nm  = entry.get('bin_name', str(entry))
            else:
                cp_key, cp_kind, bin_nm = 'bins', 'Coverpoint', str(entry)

            if cp_key not in by_coverpoint:
                by_coverpoint[cp_key] = {'kind': cp_kind, 'bins': []}
            by_coverpoint[cp_key]['bins'].append(bin_nm)

        for cp_name, cp_data in by_coverpoint.items():
            feedback.append(f"  {cp_data['kind']}: `{cp_name}`")
            for bin_nm in cp_data['bins']:
                feedback.append(f"    - `{bin_nm}`")
            feedback.append("")

    feedback.append("\n### What to do next:")
    feedback.append(
        "1. Check the sample event — if coverage uses `@(posedge clk)`, "
        "stimulus must allow the clock to tick with the right signal values BEFORE the edge."
    )
    feedback.append(
        "2. Target the coverpoint — understand what signal each coverpoint measures, "
        "then drive that signal to the bin's required value."
    )
    feedback.append(
        "3. Use the bin name to infer the condition needed "
        "(e.g. `neg_one` → set operand to -1, `invalid[8]` → set opcode to 4'h8)."
    )
    feedback.append(
        "4. Focus on lowest coverage covergroups first."
    )

    return "\n".join(feedback)


def _create_annotated_source(uncovered_lines: Dict[str, list[int]], max_holes: int = 0) -> str:
    """Create annotated source highlighting high-priority uncovered lines,
    grouped by module with total uncovered counts.

    Args:
        uncovered_lines: Mapping of file paths to lists of uncovered line numbers.
        max_holes: Maximum number of priority holes to include.
            0 or negative means unbounded (show all holes).

    Returns:
        Grouped annotated snippets with summary header, or empty string
        if there are no uncovered lines.
    """
    unbounded = max_holes <= 0

    if not uncovered_lines:
        return "All lines covered!"

    # Total uncovered hole count across all files (before selection)
    total_uncovered = sum(len(lines) for lines in uncovered_lines.values())

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
    context_radius = getattr(_config, 'coverage_hole_radius', 5) if _config else 5
    selected = []
    for candidate in prioritized:
        if not unbounded and len(selected) >= max_holes:
            break
        c_file, c_line, _ = candidate
        # Skip if this candidate overlaps with an already-selected hole
        overlaps = False
        for s_file, s_line, _ in selected:
            if c_file == s_file and abs(c_line - s_line) <= context_radius * 2:
                overlaps = True
                break
        if not overlaps:
            selected.append(candidate)

    # Group selected holes by file, preserving insertion order
    from collections import defaultdict
    grouped: Dict[str, list] = defaultdict(list)
    for file_path, line_num, code in selected:
        grouped[file_path].append((line_num, code))

    # Build output: summary header + per-module sections
    parts = [f"Showing {len(selected)} of {total_uncovered} uncovered holes:"]

    for file_path, holes in grouped.items():
        filename = Path(file_path).name
        hole_word = "hole" if len(holes) == 1 else "holes"
        parts.append(f"# {filename}: {len(holes)} uncovered {hole_word}")

        for idx, (line_num, code) in enumerate(holes, 1):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    file_lines = f.readlines()

                # Mark the uncovered line
                file_lines[line_num - 1] = file_lines[line_num - 1].rstrip('\n') + "\t// UNCOVERED\n"

                # Extract context window (lines before and after)
                start = max(0, line_num - context_radius - 1)
                end = min(len(file_lines), line_num + context_radius)
                context = ''.join(file_lines[start:end])

                parts.append(f"{idx}: line {line_num}\n{context}")
            except:
                parts.append(f"{idx}: line {line_num}\n    {code}")

    return "\n\n".join(parts)
