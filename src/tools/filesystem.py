from pathlib import Path
from typing import Dict, Any
from langchain.tools import tool
import logging

# Global config reference (set by graph initialization)
_config = None

# Keywords that indicate forbidden testbench constructs (per system prompt)
FORBIDDEN_KEYWORDS = [
    "force ", "release ",
    "$signal_force", "$signal_release",
    "deposit",
    "$error", "$fatal",
    "$stop",
]

def set_config(config):
    """Set global config reference for tools."""
    global _config
    _config = config


def _resolve_path(path: str) -> Path:
    """Resolve a path against work_dir, then design_dir, then absolute.

    Resolution order for relative paths:
      1. work_dir / path  (testplan.md, logs/, testbenches/, etc.)
      2. design_dir / path  (rtl/foo.sv, spec.md, etc.)
      3. Path(path).resolve()  (absolute or cwd-relative fallback)

    Absolute paths are used as-is.

    Returns the resolved Path (regardless of whether it exists).
    """
    p = Path(path)
    if p.is_absolute():
        return p.resolve()

    work_candidate = (_config.work_dir / path).resolve()
    if work_candidate.exists():
        return work_candidate

    design_candidate = (_config.design_dir / path).resolve()
    if design_candidate.exists():
        return design_candidate

    # Fall back to cwd-relative; caller must handle not-found
    return p.resolve()


def _not_found_error(path: str) -> dict:
    """Return a descriptive file-not-found error with search locations."""
    work_candidate = (_config.work_dir / path).resolve()
    design_candidate = (_config.design_dir / path).resolve()
    cwd_candidate = Path(path).resolve()
    return {
        "success": False,
        "error": (
            f"File not found: '{path}'. Searched:\n"
            f"  - {work_candidate}  (work dir)\n"
            f"  - {design_candidate}  (design dir)\n"
            f"  - {cwd_candidate}  (absolute/cwd)\n"
            f"Tip: use list_directory to discover available files and their exact paths."
        ),
    }


@tool
def read_file(path: str) -> Dict[str, Any]:
    """Read the contents of a file.

    Path resolution (relative paths only):
      1. Relative to the work directory  — for testplan.md, logs/, testbenches/, coverage_tracking.md
      2. Relative to the design directory — for RTL files (e.g., rtl/foo.sv, spec.md)
      3. Absolute path                   — use the full path from your task description

    Examples:
      read_file("testplan.md")                 # → work_dir/testplan.md
      read_file("logs/compile_iter_1_gen_0.log")  # → work_dir/logs/...
      read_file("/abs/path/to/design/chacha_top.sv")  # absolute path

    Use list_directory to discover available file names before reading.

    Args:
        path: File path — relative (resolved against work_dir then design_dir) or absolute.

    Returns:
        Dictionary with success (bool), content (str on success), error (str on failure).
    """
    try:
        file_path = _resolve_path(path)

        if not file_path.exists():
            return _not_found_error(path)

        # Enforce DESIGN_CONTEXT: block RTL access if disabled
        if not _config.design_context_enabled:
            rtl_dir = (_config.design_dir / "rtl").resolve()
            if file_path.is_relative_to(rtl_dir):
                return {
                    "success": False,
                    "error": "RTL access DISABLED. Cannot read files in rtl/ directory. Use specification and module header only."
                }

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        return {"success": True, "content": content}

    except Exception as e:
        return {"success": False, "error": f"Read error: {str(e)}"}


@tool
def write_file(path: str, content: str) -> Dict[str, Any]:
    """Write content to a file in the work directory.

    Relative paths are always anchored to the work directory.
    You cannot write outside the work directory.

    Examples:
      write_file("testplan.md", ...)
      write_file("testbenches/tb_iter_3_gen_0.sv", ...)
      write_file("notes.md", ...)

    Args:
        path: Relative path within work directory (e.g., "testbenches/tb_iter_1.sv")
        content: Content to write

    Returns:
        Dictionary with success (bool), full_path (str on success), error (str on failure).
    """
    try:
        full_path = (_config.work_dir / path).resolve()

        if not full_path.is_relative_to(_config.work_dir.resolve()):
            return {
                "success": False,
                "error": f"Security violation: Path escapes work directory. Must write within {_config.work_dir}"
            }

        # Scan for forbidden testbench constructs
        violations = []
        for line_num, line in enumerate(content.split('\n'), 1):
            for kw in FORBIDDEN_KEYWORDS:
                if kw in line:
                    violations.append((kw, line_num, line.strip()))

        if violations:
            logging.warning(f"Forbidden testbench construct(s) detected in '{path}':")
            for kw, line_num, line in violations:
                logging.warning(f"  Line {line_num}: {line}")

        full_path.parent.mkdir(parents=True, exist_ok=True)

        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logging.info(f"Wrote file: {full_path}")

        return {"success": True, "full_path": str(full_path)}

    except Exception as e:
        return {"success": False, "error": f"Write error: {str(e)}"}


@tool
def list_directory(path: str) -> Dict[str, Any]:
    """List the contents of a directory.

    Path resolution (relative paths only):
      1. Relative to the work directory  — e.g., "testbenches", "logs", "coverage"
      2. Relative to the design directory — e.g., "rtl", "."
      3. Absolute path                   — use the full path

    Examples:
      list_directory("testbenches")      # → work_dir/testbenches/
      list_directory("logs")             # → work_dir/logs/
      list_directory("/abs/path/to/rtl") # absolute path to design directory
      list_directory(".")                # → work_dir (work directory root)

    Args:
        path: Directory path — relative (resolved against work_dir then design_dir) or absolute.

    Returns:
        Dictionary with success (bool), files (list), directories (list), error (str on failure).
        Each file/directory name is returned as a simple name; build the full path by
        prepending the directory path you passed in.
    """
    try:
        dir_path = _resolve_path(path)

        if not dir_path.exists():
            # Give a not-found error showing searched locations
            work_candidate = (_config.work_dir / path).resolve()
            design_candidate = (_config.design_dir / path).resolve()
            return {
                "success": False,
                "error": (
                    f"Directory not found: '{path}'. Searched:\n"
                    f"  - {work_candidate}  (work dir)\n"
                    f"  - {design_candidate}  (design dir)\n"
                    f"  - {dir_path}  (absolute/cwd)"
                ),
            }

        if not dir_path.is_dir():
            return {"success": False, "error": f"Not a directory: {dir_path}"}

        # Enforce DESIGN_CONTEXT
        if not _config.design_context_enabled:
            rtl_dir = (_config.design_dir / "rtl").resolve()
            if dir_path.is_relative_to(rtl_dir):
                return {
                    "success": False,
                    "error": "RTL access DISABLED. Cannot list rtl/ directory."
                }

        files = sorted(f.name for f in dir_path.iterdir() if f.is_file())
        directories = sorted(d.name for d in dir_path.iterdir() if d.is_dir())

        return {
            "success": True,
            "path": str(dir_path),
            "files": files,
            "directories": directories,
        }

    except Exception as e:
        return {"success": False, "error": f"List error: {str(e)}"}
