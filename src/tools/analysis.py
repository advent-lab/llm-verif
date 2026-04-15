from pathlib import Path
from typing import Dict, Any, Optional, List
from langchain.tools import tool
import logging
import re

_config = None
_adapter = None  # Simulator adapter instance
_cumulative_coverage_db: Optional[Path] = None  # Path to cumulative coverage database

def set_config(config):
    global _config, _adapter
    _config = config
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
    global _cumulative_coverage_db
    _cumulative_coverage_db = path

def get_cumulative_coverage_db() -> Optional[Path]:
    return _cumulative_coverage_db

@tool
def parse_coverage(coverage_db_path: str) -> Dict[str, Any]:
    """
    Parse coverage database and extract detailed metrics.
    Supports both QuestaSim (.ucdb) and Verilator (.dat) formats.
    Automatically merges with cumulative coverage across all iterations.

    Args:
        coverage_db_path: Path to coverage database

    Returns:
        Dictionary with success, iteration_coverage, cumulative_coverage,
        total_coverage, breakdown, uncovered_lines, annotated_source,
        cumulative_coverage_db, error
    """
    global _cumulative_coverage_db

    try:
        db_path = Path(coverage_db_path).resolve()
        if not db_path.exists():
            return {"success": False, "error": f"Coverage database not found: {coverage_db_path}"}

        logging.info("Parsing iteration coverage database")
        iteration_result = _adapter.parse_coverage(db_path)
        iteration_coverage = iteration_result.total_coverage
        logging.info(f"Iteration coverage: {iteration_coverage:.1f}%")

        coverage_dir = db_path.parent
        simulator_type = getattr(_config, 'simulator_type', 'questasim').lower()
        cumulative_db_path = coverage_dir / ("cumulative.ucdb" if simulator_type == 'questasim' else "cumulative.dat")

        try:
            _adapter.merge_cumulative_coverage(db_path, cumulative_db_path)
            _cumulative_coverage_db = cumulative_db_path
        except Exception as e:
            logging.error(f"Cumulative merge failed: {e}")
            _cumulative_coverage_db = db_path
            cumulative_db_path = db_path

        logging.info("Parsing cumulative coverage database")
        cumulative_result = _adapter.parse_coverage(cumulative_db_path)
        cumulative_coverage = cumulative_result.total_coverage
        logging.info(f"Cumulative coverage: {cumulative_coverage:.1f}%")

        max_holes = getattr(_config, 'num_feedback_holes', 3) if _config else 3
        annotated_source = _create_annotated_source(cumulative_result.uncovered_lines, max_holes)

        # Enrich uncovered_lines with actual source text
        enriched_uncovered = _enrich_uncovered_lines(cumulative_result.uncovered_lines)

        return {
            "success": True,
            "iteration_coverage": iteration_coverage,
            "cumulative_coverage": cumulative_coverage,
            "total_coverage": cumulative_coverage,
            "breakdown": cumulative_result.breakdown,
            "uncovered_lines": enriched_uncovered,
            "annotated_source": annotated_source,
            "cumulative_coverage_db": str(cumulative_db_path)
        }

    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}
    except RuntimeError as e:
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

    Args:
        coverage_db_path: Path to coverage database (.ucdb for QuestaSim)

    Returns:
        Dictionary with success, total_coverage, iteration_coverage,
        cumulative_coverage, covergroups, feedback, uncovered_bins,
        cumulative_coverage_db, error
    """
    global _cumulative_coverage_db

    try:
        from ..utils.questasim import parse_functional_coverage_text

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

        logging.info("Generating functional coverage report from cumulative database")
        report_path = coverage_dir / "cumulative_functional_coverage.txt"

        import subprocess
        vcover_cmd = [
            str(_adapter.simulator_path / "vcover"),
            "report", "-details",
            "-output", str(report_path),
            str(cumulative_db_path)
        ]

        try:
            subprocess.run(vcover_cmd, check=True, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Coverage report generation timed out"}
        except subprocess.CalledProcessError as e:
            return {"success": False, "error": f"Coverage report generation failed: {e.stderr}"}

        logging.info(f"Parsing cumulative functional coverage report: {report_path}")
        result = parse_functional_coverage_text(report_path)

        if 'error' in result:
            return {"success": False, "error": result['error']}

        cumulative_coverage = result['total_coverage']
        covergroups = result['covergroups']

        feedback = _generate_functional_coverage_feedback(cumulative_coverage, covergroups)

        # Flatten uncovered bins — now carries enriched fields from the
        # rewritten parse_functional_coverage_text
        all_uncovered_bins = []
        for cg in covergroups:
            for bin_entry in cg.get('uncovered_bins', []):
                if isinstance(bin_entry, dict):
                    # New enriched format from rewritten parser
                    all_uncovered_bins.append({
                        'covergroup':       cg['name'],
                        'instance_path':    cg.get('instance_path', ''),
                        'coverpoint':       bin_entry.get('coverpoint', ''),
                        'coverpoint_kind':  bin_entry.get('coverpoint_kind', 'Coverpoint'),
                        'bin_name':         bin_entry.get('bin_name', ''),
                        'covergroup_coverage': cg.get('coverage', 0.0),
                        'sample_event':     cg.get('sample_event'),
                    })
                else:
                    # Legacy string format fallback
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


# ── Helpers ────────────────────────────────────────────────────────────────────

def _enrich_uncovered_lines(
    uncovered_lines: Dict[str, list]
) -> Dict[str, List[Dict]]:
    """
    Convert the raw {file: [line_nums]} dict into an enriched form that
    includes the actual source text for each uncovered line.

    Returns:
        {
          "/path/to/file.v": [
              {"line": 248, "text": "  a_new = H0_reg;"},
              {"line": 249, "text": "  b_new = H1_reg;"},
              ...
          ]
        }

    If a source file cannot be read the line text is set to
    "(source unavailable)" so the structure remains consistent.
    """
    enriched: Dict[str, List[Dict]] = {}
    for file_path, line_nums in uncovered_lines.items():
        source_lines: Optional[List[str]] = None
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as fh:
                source_lines = fh.readlines()
        except OSError:
            pass

        entries = []
        for ln in sorted(line_nums):
            if source_lines and 1 <= ln <= len(source_lines):
                text = source_lines[ln - 1].rstrip()
            else:
                text = "(source unavailable)"
            entries.append({"line": ln, "text": text})

        enriched[file_path] = entries

    return enriched


def _generate_functional_coverage_feedback(
    total_coverage: float,
    covergroups: List[Dict]
) -> str:
    """
    Generate enriched human-readable feedback about uncovered bins.

    For each incomplete covergroup the feedback shows:
    - Covergroup name, instance path, coverage %, and sample event
    - Bins grouped under their parent coverpoint with the coverpoint kind
    - Actionable step-by-step guidance

    Args:
        total_coverage: Total functional coverage percentage
        covergroups:    List of covergroup dicts from parse_functional_coverage_text

    Returns:
        Formatted feedback string for the LLM
    """
    if total_coverage >= 99.9:
        return "✓ Functional coverage complete! All bins have been hit."

    feedback = [f"## Functional Coverage: {total_coverage:.1f}%\n"]

    # Incomplete covergroups — those with at least one uncovered bin entry
    incomplete_cgs = [cg for cg in covergroups if cg.get('uncovered_bins')]

    if not incomplete_cgs:
        return "✓ All bins covered (or no functional coverage defined)."

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

        # Sample event — critical for understanding when coverage is recorded
        if sample_event:
            feedback.append(
                f"  Sampled: `{sample_event}`  "
                f"*(coverage is only recorded when this event fires)*"
            )
        else:
            feedback.append(
                "  Sampled: implicit (called via .sample() in testbench)"
            )

        feedback.append(f"  Missing {len(uncovered)} bin(s):\n")

        # Group bins by coverpoint for clarity
        # uncovered_bins is now a list of dicts: {coverpoint, coverpoint_kind, bin_name}
        # or legacy strings
        by_coverpoint: Dict[str, Dict] = {}
        for entry in uncovered:
            if isinstance(entry, dict):
                cp_key  = entry.get('coverpoint', 'unknown')
                cp_kind = entry.get('coverpoint_kind', 'Coverpoint')
                bin_nm  = entry.get('bin_name', str(entry))
            else:
                # Legacy flat string
                cp_key  = 'bins'
                cp_kind = 'Coverpoint'
                bin_nm  = str(entry)

            if cp_key not in by_coverpoint:
                by_coverpoint[cp_key] = {'kind': cp_kind, 'bins': []}
            by_coverpoint[cp_key]['bins'].append(bin_nm)

        for cp_name, cp_data in by_coverpoint.items():
            kind_label = cp_data['kind']
            feedback.append(f"  {kind_label}: `{cp_name}`")
            for bin_nm in cp_data['bins']:
                feedback.append(f"    - `{bin_nm}`")
            feedback.append("")

    # Actionable guidance
    feedback.append("\n### What to do next:")
    feedback.append(
        "1. **Check the sample event** — if coverage uses `@(posedge clk)`, "
        "your stimulus must allow the clock to tick with the right signal "
        "values present BEFORE the edge fires."
    )
    feedback.append(
        "2. **Target the coverpoint** — understand what signal/expression "
        "each coverpoint measures, then drive that signal to the bin's "
        "required value."
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


def _create_annotated_source(
    uncovered_lines: Dict[str, list],
    max_holes: int = 3
) -> str:
    """
    Create annotated source snippets highlighting high-priority uncovered lines.

    Each hole shows 5 lines of context before and after the uncovered line,
    with the uncovered line marked with a comment. The actual source text of
    the uncovered line is always included.

    Args:
        uncovered_lines: Mapping of file paths to uncovered line numbers
                         (raw list of ints OR enriched list of dicts).
        max_holes:       Maximum number of snippet holes to include.

    Returns:
        Combined annotated snippets, or empty string if max_holes is 0.
    """
    if max_holes == 0:
        return ""

    if not uncovered_lines:
        return "All lines covered!"

    # Normalise: accept both raw int lists and enriched dict lists
    normalised: Dict[str, List[int]] = {}
    for file_path, entries in uncovered_lines.items():
        if entries and isinstance(entries[0], dict):
            normalised[file_path] = [e['line'] for e in entries]
        else:
            normalised[file_path] = list(entries)

    # Prioritize control-flow statements
    prioritized = []
    for file_path, line_nums in normalised.items():
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                file_lines = f.readlines()
            for line_num in line_nums:
                if 1 <= line_num <= len(file_lines):
                    code = file_lines[line_num - 1].strip()
                    if re.search(r'\b(if|case|while|for)\s*\(', code):
                        prioritized.insert(0, (file_path, line_num, code))
                    else:
                        prioritized.append((file_path, line_num, code))
        except Exception:
            continue

    if not prioritized:
        return "Uncovered lines found but could not read source"

    context_radius = 5
    selected = []
    for candidate in prioritized:
        if len(selected) >= max_holes:
            break
        c_file, c_line, _ = candidate
        overlaps = any(
            c_file == s_file and abs(c_line - s_line) <= context_radius * 2
            for s_file, s_line, _ in selected
        )
        if not overlaps:
            selected.append(candidate)

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

            start   = max(0, line_num - context_radius - 1)
            end     = min(len(file_lines), line_num + context_radius)
            context = ''.join(file_lines[start:end])
            snippets.append(f"{header}\n{context}")
        except Exception:
            snippets.append(
                f"{header}\nUncovered line: {file_path}:{line_num} - {code}"
            )

    return "\n\n".join(snippets)
