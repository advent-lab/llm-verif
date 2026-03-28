from pathlib import Path
from typing import Dict, Any
from langchain.tools import tool
import logging
import re
import shutil

# Global config reference (set by graph initialization)
_config = None

def set_config(config):
    """Set global config reference for tools."""
    global _config
    _config = config

@tool
def read_file(path: str) -> Dict[str, Any]:
    """
    Read the contents of a file.

    Args:
        path: Path to file (relative to project root or absolute)

    Returns:
        Dictionary with success, content (if successful), error (if failed)

    Use this tool to:
    - Read the design specification
    - Read RTL files (if design context is enabled)
    - Review previous testbenches
    - Read compilation or simulation logs
    """
    try:
        file_path = Path(path).resolve()

        # Enforce DESIGN_CONTEXT: block RTL access if disabled
        if not _config.design_context_enabled:
            rtl_dir = (_config.design_dir / "rtl").resolve()
            if file_path.is_relative_to(rtl_dir):
                return {
                    "success": False,
                    "error": "RTL access DISABLED. Cannot read files in rtl/ directory. Use specification and module header only."
                }

        # Read file
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Truncate large files to stay within token budget
        char_limit = getattr(_config, 'read_file_token_limit', 0)
        if char_limit > 0 and len(content) > char_limit:
            truncated = content[:char_limit]
            original_size = len(content)
            hint = ""
            if "coverage" in str(file_path).lower():
                hint = (
                    " This is a coverage report — use parse_coverage or "
                    "parse_functional_coverage tools instead for a compact summary."
                )
            return {
                "success": True,
                "content": truncated,
                "truncated": True,
                "warning": (
                    f"File truncated: showing {char_limit} of {original_size} chars "
                    f"({original_size - char_limit} chars omitted).{hint}"
                )
            }

        return {
            "success": True,
            "content": content
        }

    except FileNotFoundError:
        return {"success": False, "error": f"File not found: {path}"}
    except Exception as e:
        return {"success": False, "error": f"Read error: {str(e)}"}

@tool
def write_file(path: str, content: str) -> Dict[str, Any]:
    """
    Write content to a file in the work directory.

    FUNCTIONAL COVERAGE MODE:
    - If functional_coverage_enabled=True, this tool handles STIMULUS INJECTION
    - It loads the user's testbench, extracts the stimulus section, and replaces it
    - The user's testbench MUST have // BEGIN_STIMULUS and // END_STIMULUS markers

    NORMAL MODE (Code Coverage):
    - Creates a new testbench file from scratch

    Args:
        path: Relative path within work directory (e.g., "testbenches/tb_iter_1.sv")
        content: Content to write (full testbench OR stimulus code depending on mode)

    Returns:
        Dictionary with success, full_path (if successful), error (if failed)

    Use this tool to:
    - Save testplans (e.g., "testplan.md")
    - Save testbenches (e.g., "testbenches/tb_iter_1.sv")
    - In functional coverage mode: inject stimulus into user's template

    NOTE: You can ONLY write to the work directory.
    """
    try:
        # Check modes
        uvm_enabled = getattr(_config, 'uvm_enabled', False)
        funcov_enabled = getattr(_config, 'functional_coverage_enabled', False)

        if uvm_enabled and path.endswith('.sv'):
            # UVM MODE: Full file write + snapshot for iteration tracking
            result = _write_full_file(path, content)
            if result.get("success"):
                _save_uvm_iteration_snapshot(path, content)
            return result
        elif funcov_enabled and path.endswith('.sv'):
            # FUNCTIONAL COVERAGE MODE: Inject stimulus into user's testbench
            return _inject_stimulus_into_testbench(path, content)
        else:
            # NORMAL MODE: Write full file (testbench or testplan)
            return _write_full_file(path, content)

    except Exception as e:
        logging.error(f"Write file error: {e}")
        return {"success": False, "error": str(e)}


def _write_full_file(path: str, content: str) -> Dict[str, Any]:
    """Normal mode: Write a complete file (testbench, testplan, etc.)."""
    try:
        # Construct full path within work directory
        full_path = (_config.work_dir / path).resolve()

        # Security: Prevent directory traversal
        if not full_path.is_relative_to(_config.work_dir.resolve()):
            return {
                "success": False,
                "error": f"Security violation: Path escapes work directory. Must write within {_config.work_dir}"
            }

        # Create parent directories if needed
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logging.info(f"Wrote file: {full_path}")

        return {
            "success": True,
            "full_path": str(full_path)
        }

    except Exception as e:
        logging.error(f"Write file error: {e}")
        return {"success": False, "error": str(e)}


def _save_uvm_iteration_snapshot(path: str, content: str):
    """Save a copy of the written UVM file into an iteration snapshot folder.

    Creates work_dir/iterations/iter_N/<filename> so users can observe
    how the generated sequences and test evolve across iterations.
    """
    try:
        iteration = getattr(_config, 'current_iteration', 1)
        snapshot_dir = _config.work_dir / "iterations" / f"iter_{iteration}"
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        # Use just the filename (strip any subdirectory like "testbenches/")
        filename = Path(path).name
        snapshot_path = snapshot_dir / filename

        with open(snapshot_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logging.info(f"UVM iteration snapshot saved: {snapshot_path}")
    except Exception as e:
        logging.warning(f"Failed to save UVM iteration snapshot: {e}")


def _inject_stimulus_into_testbench(path: str, content: str) -> Dict[str, Any]:
    """
    Functional coverage mode: Load user's testbench and inject new stimulus.
    
    This function:
    1. Loads the user's functional coverage testbench template
    2. Extracts new stimulus from agent's content (between markers or entire content)
    3. Replaces the stimulus section in the template
    4. Writes the modified testbench to the work directory
    
    Args:
        path: Destination path for the modified testbench (relative to work_dir)
        content: Either full testbench with markers OR just stimulus code
    
    Returns:
        Success dict with path to modified testbench
    """
    try:
        # Get the user's functional coverage testbench template
        user_tb_path = _config.functional_coverage_testbench_path
        
        if not user_tb_path or not user_tb_path.exists():
            return {
                "success": False,
                "error": f"Functional coverage testbench not found: {user_tb_path}. "
                        f"Set FUNCTIONAL_COVERAGE_TESTBENCH in .env or add to dashboard.json"
            }
        
        # Load the user's testbench template
        logging.info(f"Loading functional coverage testbench template: {user_tb_path}")
        with open(user_tb_path, 'r', encoding='utf-8') as f:
            template = f.read()
        
        # Check if template has required markers
        if '// BEGIN_STIMULUS' not in template or '// END_STIMULUS' not in template:
            return {
                "success": False,
                "error": "Functional coverage testbench missing // BEGIN_STIMULUS and // END_STIMULUS markers. "
                        "Please add these markers around the initial block in your testbench."
            }
        
        # Check if content is a full testbench or just stimulus
        if '// BEGIN_STIMULUS' in content and '// END_STIMULUS' in content:
            # Agent provided full testbench with markers - extract just the stimulus
            logging.info("Extracting stimulus from full testbench")
            new_stimulus = _extract_stimulus_section(content)
        else:
            # Agent provided just the stimulus code
            logging.info("Using provided content as stimulus")
            new_stimulus = content.strip()
        
        # Inject the new stimulus into the template
        logging.info("Injecting stimulus into template")
        modified_testbench = _replace_stimulus_section(template, new_stimulus)
        
        # Write the modified testbench to work directory
        full_path = (_config.work_dir / path).resolve()
        
        # Security: Prevent directory traversal
        if not full_path.is_relative_to(_config.work_dir.resolve()):
            return {
                "success": False,
                "error": f"Security violation: Path escapes work directory"
            }
        
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(modified_testbench)
        
        logging.info(f"Injected stimulus into testbench: {full_path}")
        return {
            "success": True,
            "full_path": str(full_path)
        }
    
    except Exception as e:
        logging.error(f"Stimulus injection error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return {"success": False, "error": str(e)}


def _extract_stimulus_section(testbench_content: str) -> str:
    """
    Extract the stimulus code between // BEGIN_STIMULUS and // END_STIMULUS markers.
    
    Args:
        testbench_content: Full testbench with markers
    
    Returns:
        Just the stimulus code (without markers, initial begin, or $finish)
    """
    pattern = r'// BEGIN_STIMULUS\s*\n(.*?)\n\s*// END_STIMULUS'
    match = re.search(pattern, testbench_content, re.DOTALL)
    
    if match:
        stimulus = match.group(1).strip()
        logging.debug(f"Extracted stimulus (raw): {len(stimulus)} characters")
        
        # Clean up the stimulus code
        stimulus = _clean_stimulus_code(stimulus)
        
        logging.debug(f"Extracted stimulus (cleaned): {len(stimulus)} characters")
        return stimulus
    else:
        # No markers found - return entire content as stimulus (cleaned)
        logging.warning("No BEGIN_STIMULUS/END_STIMULUS markers found in content, using entire content")
        return _clean_stimulus_code(testbench_content.strip())


def _clean_stimulus_code(stimulus: str) -> str:
    """
    Clean stimulus code by removing wrappers that are already in the template.
    
    Removes:
    - 'initial begin' at the start
    - '$finish;' at the end  
    - 'end' at the very end
    - Extra whitespace
    
    Args:
        stimulus: Raw stimulus code from agent
    
    Returns:
        Cleaned stimulus code (pure assignments/logic only)
    """
    lines = stimulus.split('\n')
    cleaned_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        # Skip lines that are template wrappers
        if stripped in ['initial begin', 'end', '$finish;', '$finish']:
            continue
        
        # Skip pure comment lines that are just markers
        if stripped.startswith('//') and any(marker in stripped for marker in [
            'BEGIN_STIMULUS', 'END_STIMULUS', 'TODO:', 'AGENT:', 
            '============', 'Format:', 'Example'
        ]):
            continue
            
        cleaned_lines.append(line)
    
    # Join back and clean up excessive whitespace
    cleaned = '\n'.join(cleaned_lines).strip()
    
    # Remove multiple blank lines
    while '\n\n\n' in cleaned:
        cleaned = cleaned.replace('\n\n\n', '\n\n')
    
    return cleaned


def _replace_stimulus_section(template: str, new_stimulus: str) -> str:
    """
    Replace the stimulus section in the template with new stimulus code.
    
    Preserves:
    - All covergroups and coverpoints
    - DUT instantiation
    - Signal declarations
    - initial begin...end wrapper
    - $finish; statement
    - Everything outside the markers
    
    Replaces:
    - Only the stimulus code INSIDE the initial begin...end block
    
    Args:
        template: User's testbench with // BEGIN_STIMULUS and // END_STIMULUS markers
        new_stimulus: New stimulus code to inject
    
    Returns:
        Modified testbench with new stimulus
    
    Raises:
        ValueError: If markers not found in template
    """
    # Verify markers exist
    if '// BEGIN_STIMULUS' not in template or '// END_STIMULUS' not in template:
        raise ValueError(
            "Testbench template missing // BEGIN_STIMULUS and // END_STIMULUS markers"
        )
    
    # Pattern to match the content between markers, capturing the initial begin...end structure
    # Group 1: Everything before initial begin content (including "initial begin" line)
    # Group 2: The old stimulus content (what we'll replace)
    # Group 3: Everything after stimulus content (including "$finish; end" and markers)
    pattern = r'(// BEGIN_STIMULUS\s*\n\s*initial begin\s*\n(?:.*?\n)*?)(.*?)(\s*\$finish;\s*\n\s*end\s*\n\s*// END_STIMULUS)'
    
    # Check if pattern matches (template has initial begin...end structure)
    match = re.search(pattern, template, re.DOTALL)
    
    if match:
        # Template has initial begin...end structure - inject inside it
        before_stimulus = match.group(1)
        after_stimulus = match.group(3)
        
        # Add proper indentation to new stimulus (4 spaces)
        indented_stimulus = '\n'.join('        ' + line if line.strip() else '' 
                                       for line in new_stimulus.split('\n'))
        
        replacement = f'{before_stimulus}{indented_stimulus}{after_stimulus}'
        
        # Replace the matched section
        modified = template[:match.start()] + replacement + template[match.end():]
        
        logging.info("Successfully replaced stimulus inside initial begin...end block")
    else:
        # Fallback: Template doesn't have expected structure, replace everything between markers
        logging.warning("Template doesn't have expected initial begin...end structure, using simple replacement")
        pattern_simple = r'(// BEGIN_STIMULUS\s*\n).*?(\n\s*// END_STIMULUS)'
        
        # Wrap stimulus in initial begin...end if not present
        wrapped_stimulus = f'    initial begin\n        {new_stimulus}\n        $finish;\n    end'
        replacement_simple = f'\\1{wrapped_stimulus}\\2'
        
        modified = re.sub(pattern_simple, replacement_simple, template, flags=re.DOTALL)
        logging.info("Added initial begin...end wrapper around stimulus")
    
    # Verify replacement worked
    if modified == template:
        logging.error("Stimulus replacement did not modify template - check pattern matching")
    
    return modified


@tool
def request_infra_modification() -> Dict[str, Any]:
    """
    Request permission to modify the UVM driver file.

    Call this when you believe the current driver protocol is preventing
    coverage bins from being hit (e.g., single-cycle cs prevents back-to-back
    transitions, timing prevents state overlaps).

    Once granted, you can use write_file to save a modified driver to
    testbenches/<driver_filename>. The modified driver will be used in
    subsequent compilations. You should also update your sequences to
    leverage the new driver protocol.

    Returns:
        Dictionary with success, driver_content (original driver source),
        driver_filename (where to save modifications), or error if not
        available.
    """
    try:
        if not getattr(_config, 'uvm_enabled', False):
            return {
                "success": False,
                "error": "Infrastructure modification is only available in UVM mode."
            }

        driver_file = getattr(_config, 'uvm_driver_file', None)
        if not driver_file:
            return {
                "success": False,
                "error": "No driver file detected. Cannot enable infrastructure modification."
            }

        # Read the original driver content
        driver_content = ""
        if driver_file.exists():
            driver_content = driver_file.read_text()

        driver_filename = driver_file.name
        work_driver = _config.work_dir / "testbenches" / driver_filename

        logging.info(f"Infrastructure modification GRANTED for driver: {driver_filename}")

        return {
            "success": True,
            "infra_modification_granted": True,
            "driver_filename": driver_filename,
            "driver_path": f"testbenches/{driver_filename}",
            "driver_content": driver_content,
            "instructions": (
                f"You may now modify the driver. Save your changes using:\n"
                f"  write_file(\"testbenches/{driver_filename}\", <new_content>)\n"
                f"After modifying the driver, update your sequences to use the "
                f"new protocol, then compile and simulate as usual.\n"
                f"You can iterate on the driver across multiple cycles."
            ),
        }

    except Exception as e:
        logging.error(f"Infrastructure modification request error: {e}")
        return {"success": False, "error": str(e)}


@tool
def plan_coverage_strategy(target_bins: str, strategy: str) -> Dict[str, Any]:
    """
    Plan your stimulus strategy BEFORE writing sequence/test files.

    Call this tool after analyzing coverage results (parse_coverage /
    parse_functional_coverage) and BEFORE calling write_file. It forces you
    to think through which bins to target and how, producing better stimulus.

    Args:
        target_bins: List the specific uncovered bins or code lines you will
            target in this iteration. Be concrete — use bin names from the
            functional coverage report or line numbers from annotated source.
        strategy: For each target, describe the stimulus approach:
            - What sequence type (constrained random, directed, mixed)?
            - What field values / constraints will hit the bin?
            - Any seq_item constraints to bypass via direct assignment?
            - How many transactions needed?

    Returns:
        Your plan echoed back as confirmation. Proceed to write_file next.
    """
    if not target_bins.strip() or not strategy.strip():
        return {
            "success": False,
            "error": "Both target_bins and strategy must be non-empty. "
                     "Analyze the coverage report and identify specific targets."
        }

    return {
        "success": True,
        "plan_accepted": True,
        "target_bins": target_bins,
        "strategy": strategy,
        "next_step": "Now call write_file to generate the sequence and test files "
                     "implementing this strategy."
    }


@tool
def list_directory(path: str) -> Dict[str, Any]:
    """
    List contents of a directory.

    Args:
        path: Directory path

    Returns:
        Dictionary with success, files, directories (if successful), error (if failed)
    """
    try:
        dir_path = Path(path).resolve()

        # Enforce DESIGN_CONTEXT
        if not _config.design_context_enabled:
            rtl_dir = (_config.design_dir / "rtl").resolve()
            if dir_path.is_relative_to(rtl_dir):
                return {
                    "success": False,
                    "error": "RTL access DISABLED. Cannot list rtl/ directory."
                }

        if not dir_path.is_dir():
            return {"success": False, "error": f"Not a directory: {path}"}

        files = [f.name for f in dir_path.iterdir() if f.is_file()]
        directories = [d.name for d in dir_path.iterdir() if d.is_dir()]

        return {
            "success": True,
            "files": sorted(files),
            "directories": sorted(directories)
        }

    except Exception as e:
        return {"success": False, "error": f"List error: {str(e)}"}
