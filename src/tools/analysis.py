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
def parse_functional_coverage(coverage_report_path: str) -> Dict[str, Any]:
    """
    Parse functional coverage report and generate feedback for uncovered bins.
    
    This tool is used in FUNCTIONAL COVERAGE MODE to analyze which coverage bins
    have not been hit and provide actionable feedback to guide stimulus generation.
    
    Args:
        coverage_report_path: Path to text-based functional coverage report
            Generated by: vcover report -details -output <path> <ucdb_file>
    
    Returns:
        Dictionary with:
        - success: bool
        - total_coverage: float (0-100) - Overall functional coverage percentage
        - covergroups: list of covergroup details with uncovered bins
        - feedback: str (human-readable guidance for the LLM)
        - uncovered_bins: list of all uncovered bins with context
        - error: str (if failed)
    
    Example return value:
        {
            "success": True,
            "total_coverage": 45.2,
            "covergroups": [
                {
                    "name": "cg_alu_inst",
                    "coverage": 30.5,
                    "uncovered_bins": ["invalid[8]", "power_of_2[1024]", ...]
                }
            ],
            "feedback": "## Functional Coverage: 45.2%\\n...",
            "uncovered_bins": [
                {"covergroup": "cg_alu_inst", "bin_name": "invalid[8]"},
                ...
            ]
        }
    """
    try:
        from ..utils.questasim import parse_functional_coverage_text
        
        report_path = Path(coverage_report_path).resolve()
        if not report_path.exists():
            return {
                "success": False,
                "error": f"Functional coverage report not found: {coverage_report_path}"
            }
        
        # Parse the report using QuestaSim text parser
        logging.info(f"Parsing functional coverage report: {report_path}")
        result = parse_functional_coverage_text(report_path)
        
        if 'error' in result:
            return {
                "success": False,
                "error": result['error']
            }
        
        total_coverage = result['total_coverage']
        covergroups = result['covergroups']
        
        # Generate human-readable feedback for the LLM
        feedback = _generate_functional_coverage_feedback(total_coverage, covergroups)
        
        # Flatten uncovered bins for easy access
        all_uncovered_bins = []
        for cg in covergroups:
            for bin_name in cg.get('uncovered_bins', []):
                all_uncovered_bins.append({
                    'covergroup': cg['name'],
                    'bin_name': bin_name
                })
        
        logging.info(f"Functional coverage: {total_coverage:.1f}% ({len(all_uncovered_bins)} bins uncovered)")
        
        return {
            "success": True,
            "total_coverage": total_coverage,
            "covergroups": covergroups,
            "feedback": feedback,
            "uncovered_bins": all_uncovered_bins
        }
    
    except Exception as e:
        logging.error(f"Functional coverage parsing error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return {"success": False, "error": str(e)}


def _generate_functional_coverage_feedback(total_coverage: float, 
                                          covergroups: List[Dict]) -> str:
    """
    Generate human-readable feedback about uncovered bins.
    
    This feedback guides the LLM in generating stimulus to hit uncovered bins.
    
    Args:
        total_coverage: Total functional coverage percentage
        covergroups: List of covergroup dictionaries with uncovered bins
    
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
    
    feedback.append(f"### Uncovered Bins ({len(incomplete_cgs)} covergroups need work)\n")
    
    # Show details for up to 5 covergroups
    for cg in incomplete_cgs[:5]:
        cg_name = cg['name']
        cg_coverage = cg['coverage']
        uncovered = cg['uncovered_bins']
        
        feedback.append(f"**{cg_name}** ({cg_coverage:.1f}% covered)")
        feedback.append(f"  Missing {len(uncovered)} bins:")
        
        # Show up to 10 uncovered bins per covergroup
        for bin_name in uncovered[:10]:
            feedback.append(f"    - `{bin_name}`")
        
        if len(uncovered) > 10:
            feedback.append(f"    ... and {len(uncovered) - 10} more bins")
        
        feedback.append("")  # Blank line
    
    # Add actionable guidance
    feedback.append("\n### Recommended Actions:")
    feedback.append("1. Analyze uncovered bin names to understand what stimulus patterns are missing")
    feedback.append("2. Generate stimulus that targets these specific bins")
    feedback.append("3. Use constrained random or directed tests to hit corner cases")
    feedback.append("4. Focus on covergroups with lowest coverage first")
    
    return "\n".join(feedback)

def _create_annotated_source(uncovered_lines: Dict[str, list[int]], max_holes: int = 3) -> str:
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
    # Context window is 5 lines before + 5 lines after = 11 line span.
    context_radius = 5
    selected = []
    for candidate in prioritized:
        if len(selected) >= max_holes:
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

    # Build snippets for each selected hole
    snippets = []
    total = len(selected)
    for idx, (file_path, line_num, code) in enumerate(selected, 1):
        header = f"--- Hole {idx}/{total}: {Path(file_path).name}:{line_num} ---"
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                file_lines = f.readlines()

            # Mark the uncovered line
            file_lines[line_num - 1] = file_lines[line_num - 1].rstrip('\n') + "\t// ##### UNCOVERED - TARGET THIS LINE #####\n"

            # Extract context window (5 lines before and after)
            start = max(0, line_num - context_radius - 1)
            end = min(len(file_lines), line_num + context_radius)
            context = ''.join(file_lines[start:end])

            snippets.append(f"{header}\n{context}")
        except:
            snippets.append(f"{header}\nUncovered line: {file_path}:{line_num} - {code}")

    return "\n\n".join(snippets)