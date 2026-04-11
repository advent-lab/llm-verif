from typing import Dict, Any
from pathlib import Path
from langchain.tools import tool
import os


@tool
def list_directory(path: str) -> Dict[str, Any]:
    """
    List contents of a directory.
    
    Args:
        path: Path to directory to list
        
    Returns:
        Dictionary with directory contents
    """
    try:
        dir_path = Path(path)
        
        if not dir_path.exists():
            return {
                "success": False,
                "error": f"Directory does not exist: {path}"
            }
            
        if not dir_path.is_dir():
            return {
                "success": False,
                "error": f"Path is not a directory: {path}"
            }
        
        contents = []
        for item in sorted(dir_path.iterdir()):
            item_type = "directory" if item.is_dir() else "file"
            contents.append({
                "name": item.name,
                "type": item_type,
                "path": str(item)
            })
        
        return {
            "success": True,
            "path": str(dir_path),
            "contents": contents,
            "count": len(contents)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to list directory: {str(e)}"
        }


@tool
def read_file(path: str) -> Dict[str, Any]:
    """
    Read contents of a file.
    
    Args:
        path: Path to file to read
        
    Returns:
        Dictionary with file contents
    """
    try:
        file_path = Path(path)
        
        if not file_path.exists():
            return {
                "success": False,
                "error": f"File does not exist: {path}"
            }
            
        if not file_path.is_file():
            return {
                "success": False,
                "error": f"Path is not a file: {path}"
            }
        
        # Read file contents
        with open(file_path, 'r') as f:
            contents = f.read()
        
        return {
            "success": True,
            "path": str(file_path),
            "contents": contents,
            "lines": len(contents.split('\n'))
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to read file: {str(e)}"
        }


@tool
def write_file(path: str, contents: str) -> Dict[str, Any]:
    """
    Write contents to a file.
    
    Args:
        path: Path where file should be written
        contents: Content to write to file
        
    Returns:
        Dictionary indicating success/failure
    """
    try:
        file_path = Path(path)
        
        # Create parent directories if they don't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        with open(file_path, 'w') as f:
            f.write(contents)
        
        return {
            "success": True,
            "path": str(file_path),
            "message": f"Successfully wrote {len(contents)} characters to {file_path.name}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to write file: {str(e)}"
        }


@tool
def signal_done(reason: str) -> Dict[str, Any]:
    """
    Signal verification completion. Framework validates termination conditions.
    
    CRITICAL: Only call this when you believe termination conditions are met.
    The framework will validate your request and may reject it.
    
    Args:
        reason: Why you're stopping. Must be one of:
            - "coverage_complete": Achieved 100% coverage
            - "no_progress": Hit MAX_NO_PROGRESS limit (tried many iterations with no improvement)
            - "max_iterations": Reached iteration limit
    
    Returns:
        Dictionary - framework handles actual termination validation
    """
    valid_reasons = ["coverage_complete", "no_progress", "max_iterations"]
    
    if reason not in valid_reasons:
        return {
            "success": False,
            "error": f"Invalid reason '{reason}'. Must be one of: {valid_reasons}",
            "instruction": "Use a valid termination reason."
        }
    
    # Always return rejection with clear instructions
    # The framework validates actual termination conditions in react.py routing logic
    # This prevents infinite loops where agent sees success and keeps calling signal_done
    return {
        "success": False,
        "message": f"Termination request '{reason}' received but REJECTED by framework: Termination conditions not yet met.",
        "instruction": "You must continue working. Generate a NEW testbench targeting uncovered lines/bins. Analyze the latest coverage report, identify gaps, and create stimulus to hit those areas. Do NOT call signal_done again until you've made multiple more attempts to improve coverage.",
        "next_action": "Read coverage report → Identify uncovered areas → Generate new testbench → Compile → Simulate → Check coverage → Repeat"
    }
