from pathlib import Path
from typing import Dict, Any, Optional
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
        db_path = Path(coverage_db_path)
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
        annotated_source = _create_annotated_source(cumulative_result.uncovered_lines)

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

def _create_annotated_source(uncovered_lines: Dict[str, list[int]]) -> str:
    """Create annotated source highlighting high-priority uncovered lines."""
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

    # Show top priority uncovered line with context
    file_path, line_num, code = prioritized[0]

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        # Mark the uncovered line
        lines[line_num - 1] = lines[line_num - 1].rstrip('\n') + "\t// ##### UNCOVERED - TARGET THIS LINE #####\n"

        # Extract module context (5 lines before and after)
        start = max(0, line_num - 6)
        end = min(len(lines), line_num + 5)
        context = ''.join(lines[start:end])

        return f"Priority uncovered line in {Path(file_path).name}:{line_num}\n\n{context}"

    except:
        return f"Uncovered line: {file_path}:{line_num} - {code}"
