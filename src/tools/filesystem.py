from pathlib import Path
from typing import Dict, Any
from langchain.tools import tool
import logging

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

    Args:
        path: Relative path within work directory (e.g., "testbenches/tb_iter_1.sv")
        content: Content to write

    Returns:
        Dictionary with success, full_path (if successful), error (if failed)

    Use this tool to:
    - Save testplans (e.g., "testplan.md")
    - Save testbenches (e.g., "testbenches/tb_iter_1.sv")

    NOTE: You can ONLY write to the work directory.
    """
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
        return {"success": False, "error": f"Write error: {str(e)}"}

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
