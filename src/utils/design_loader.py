from pathlib import Path
import re
from typing import Tuple, List, Dict

def extract_module_header(rtl_file: Path) -> str:
    """
    Extract module header from Verilog/SystemVerilog file.

    Returns module declaration including port list and extended I/O declarations.
    Based on legacy environment.py pattern.

    Args:
        rtl_file: Path to RTL file (.v or .sv)

    Returns:
        String containing module header, or error message if not found
    """
    with open(rtl_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    start_line = None
    end_line = None
    inside_module = False
    capturing_ports = False

    for i, line in enumerate(lines):
        # Find module start
        if re.match(r"\s*module\s+\w+", line) and start_line is None:
            start_line = i
            inside_module = True

        # Find module header end (closing parenthesis with semicolon)
        if inside_module and re.search(r"\);\s*$", line):
            end_line = i
            inside_module = False
            capturing_ports = True
            continue

        # Capture extended port declarations after header
        if capturing_ports:
            if re.match(r"\s*(input|output|inout|parameter)\s+", line):
                end_line = i
            else:
                break  # Stop at first non-port line

    if start_line is not None and end_line is not None:
        return "".join(lines[start_line:end_line + 1]).strip()
    else:
        return "No module header found."


def extract_all_module_headers(design_files: List[Path]) -> str:
    """
    Extract module headers from all design files.

    For designs with multiple files, extracts headers from each and combines them.
    The first file is assumed to be the top-level module (DUT).

    Args:
        design_files: List of RTL file paths

    Returns:
        Combined string with all module headers, separated by newlines
    """
    if not design_files:
        return "No design files provided."

    headers = []

    for i, rtl_file in enumerate(design_files):
        prefix = "TOP MODULE" if i == 0 else f"MODULE {i}"
        header = extract_module_header(rtl_file)
        headers.append(f"# {prefix}: {rtl_file.name}\n{header}")

    return "\n\n".join(headers)

def scan_design_directory(design_dir: Path) -> Tuple[Path, Path, List[str]]:
    """
    Scan design directory for specification and RTL files.

    Returns:
        (spec_path, rtl_dir, rtl_files)
    """
    # Find spec (in docs/ subdirectory)
    docs_dir = design_dir / "docs"
    spec_files = list(docs_dir.glob("*.md")) + list(docs_dir.glob("*.txt"))
    if not spec_files:
        raise FileNotFoundError(f"No spec found in {docs_dir}")
    spec_path = spec_files[0]  # Use first spec file

    # Find RTL files (in rtl/ subdirectory)
    rtl_dir = design_dir / "rtl"
    rtl_files = sorted([f.name for f in rtl_dir.glob("*.v")] +
                       [f.name for f in rtl_dir.glob("*.sv")])

    if not rtl_files:
        raise FileNotFoundError(f"No RTL files found in {rtl_dir}")

    return spec_path, rtl_dir, rtl_files
