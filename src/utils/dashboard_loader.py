"""Dashboard.json loader for flexible design file discovery.

This module provides functionality to load design configurations from a centralized
dashboard.json file, which maps design names to their spec, RTL, and context files.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import os

logger = logging.getLogger(__name__)


class DesignConfig:
    """Configuration for a single design loaded from dashboard."""

    def __init__(
        self,
        design_name: str,
        spec_path: Path,
        design_files: List[Path],
        design_context_files: List[Path],
        compile_deps_files: List[Path] = None
    ):
        self.design_name = design_name
        self.spec_path = spec_path
        self.design_files = design_files
        self.design_context_files = design_context_files
        self.compile_deps_files = compile_deps_files or []

    def __repr__(self):
        return (
            f"DesignConfig(name={self.design_name}, "
            f"spec={self.spec_path.name}, "
            f"design_files={len(self.design_files)}, "
            f"context_files={len(self.design_context_files)}, "
            f"compile_deps={len(self.compile_deps_files)})"
        )


def _resolve_variables(path_str: str, variables: Dict[str, str]) -> str:
    """Resolve variable references in path strings.

    Args:
        path_str: Path string potentially containing $(VAR) references
        variables: Dictionary of variable name -> value mappings

    Returns:
        Path string with all variables resolved

    Example:
        >>> _resolve_variables("$(BASE_DIR)/design/rtl.sv", {"BASE_DIR": "/data"})
        "/data/design/rtl.sv"
    """
    result = path_str
    for var_name, var_value in variables.items():
        placeholder = f"$({var_name})"
        result = result.replace(placeholder, var_value)
    return result


def load_dashboard(dashboard_path: Path, base_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Load and parse dashboard.json file.

    Args:
        dashboard_path: Path to dashboard.json file
        base_dir: Base directory for resolving $(BASE_DIR) references
                 If None, uses dashboard parent directory

    Returns:
        Parsed dashboard dictionary

    Raises:
        FileNotFoundError: If dashboard.json doesn't exist
        ValueError: If dashboard.json is invalid JSON
    """
    if not dashboard_path.exists():
        raise FileNotFoundError(f"Dashboard file not found: {dashboard_path}")

    try:
        with open(dashboard_path, 'r') as f:
            dashboard = json.load(f)
        logger.info(f"Loaded dashboard with {len(dashboard)} design entries")
        return dashboard
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in dashboard file: {e}")


def get_design_from_dashboard(
    dashboard_path: Path,
    design_name: str,
    base_dir: Optional[Path] = None
) -> DesignConfig:
    """Load design configuration from dashboard.json.

    Args:
        dashboard_path: Path to dashboard.json file
        design_name: Name of design to load (key in dashboard)
        base_dir: Base directory for resolving $(BASE_DIR) references
                 If None, uses dashboard parent directory / data

    Returns:
        DesignConfig object with resolved paths

    Raises:
        FileNotFoundError: If dashboard or design files don't exist
        ValueError: If design_name not found in dashboard
        ValueError: If required fields (spec, design) are missing
    """
    # Load dashboard
    dashboard = load_dashboard(dashboard_path, base_dir)

    # Check if design exists
    if design_name not in dashboard:
        available = list(dashboard.keys())
        raise ValueError(
            f"Design '{design_name}' not found in dashboard. "
            f"Available designs: {', '.join(available[:5])}..."
        )

    design_entry = dashboard[design_name]
    logger.info(f"Loading design configuration for: {design_name}")

    # Determine base directory for path resolution
    if base_dir is None:
        # Default: dashboard_path/data (assuming dashboard is in LangGraph/)
        base_dir = dashboard_path.parent / "data"

    # Prepare variable substitution
    variables = {
        "BASE_DIR": str(base_dir),
        "DESIGN_NAME": design_name
    }

    # Extract and validate spec path
    spec_raw = design_entry.get("spec")
    if not spec_raw:
        raise ValueError(f"Design '{design_name}' missing required 'spec' field")

    # Handle spec as string or list
    if isinstance(spec_raw, list):
        if not spec_raw:
            raise ValueError(f"Design '{design_name}' has empty 'spec' list")
        spec_path_str = _resolve_variables(spec_raw[0], variables)
    else:
        spec_path_str = _resolve_variables(spec_raw, variables)
    
    spec_path = Path(spec_path_str)

    if not spec_path.exists():
        raise FileNotFoundError(f"Specification file not found: {spec_path}")

    logger.info(f"  Spec: {spec_path.name}")

    # Extract and validate design files (main RTL)
    design_raw = design_entry.get("design")
    if not design_raw:
        raise ValueError(f"Design '{design_name}' missing required 'design' field")

    # Handle both string and list formats
    if isinstance(design_raw, str):
        design_raw = [design_raw]
    elif not isinstance(design_raw, list):
        raise ValueError(
            f"Design '{design_name}' has invalid 'design' field type: {type(design_raw)}"
        )

    design_files = []
    for design_path_raw in design_raw:
        design_path_str = _resolve_variables(design_path_raw, variables)
        design_path = Path(design_path_str)

        if not design_path.exists():
            raise FileNotFoundError(f"Design file not found: {design_path}")

        design_files.append(design_path)
        logger.info(f"  Design: {design_path.name}")

    # Extract design_context files (optional submodules)
    design_context_raw = design_entry.get("design_context", [])

    # Handle both string and list formats
    if isinstance(design_context_raw, str):
        design_context_raw = [design_context_raw]
    elif not isinstance(design_context_raw, list):
        logger.warning(
            f"Design '{design_name}' has invalid 'design_context' field type, ignoring"
        )
        design_context_raw = []

    design_context_files = []
    for context_path_raw in design_context_raw:
        context_path_str = _resolve_variables(context_path_raw, variables)
        context_path = Path(context_path_str)

        if not context_path.exists():
            logger.warning(f"Design context file not found (skipping): {context_path}")
            continue

        design_context_files.append(context_path)
        logger.info(f"  Context: {context_path.name}")

    # Extract compile_deps files (optional, compiled but excluded from coverage)
    compile_deps_raw = design_entry.get("compile_deps", [])

    if isinstance(compile_deps_raw, str):
        compile_deps_raw = [compile_deps_raw]
    elif not isinstance(compile_deps_raw, list):
        logger.warning(
            f"Design '{design_name}' has invalid 'compile_deps' field type, ignoring"
        )
        compile_deps_raw = []

    compile_deps_files = []
    for dep_path_raw in compile_deps_raw:
        dep_path_str = _resolve_variables(dep_path_raw, variables)
        dep_path = Path(dep_path_str)

        if not dep_path.exists():
            logger.warning(f"Compile dep file not found (skipping): {dep_path}")
            continue

        compile_deps_files.append(dep_path)

    if compile_deps_files:
        logger.info(f"  Compile deps: {len(compile_deps_files)} file(s)")

    # Log summary
    logger.info(
        f"Loaded {design_name}: "
        f"{len(design_files)} design file(s), "
        f"{len(design_context_files)} context file(s), "
        f"{len(compile_deps_files)} compile dep(s)"
    )

    return DesignConfig(
        design_name=design_name,
        spec_path=spec_path,
        design_files=design_files,
        design_context_files=design_context_files,
        compile_deps_files=compile_deps_files
    )


def auto_discover_design(design_dir: Path) -> DesignConfig:
    """Auto-discover design files from directory structure.

    Fallback method when dashboard.json is not used. Scans the design
    directory for spec and RTL files.

    Args:
        design_dir: Path to design directory (must contain docs/ and rtl/)

    Returns:
        DesignConfig with discovered files

    Raises:
        FileNotFoundError: If docs/ or rtl/ directories don't exist
        ValueError: If no spec or design files found
    """
    logger.info(f"Auto-discovering design files in: {design_dir}")

    # Check directory structure
    docs_dir = design_dir / "docs"
    rtl_dir = design_dir / "rtl"

    if not docs_dir.exists():
        raise FileNotFoundError(f"Design directory missing 'docs/' subdirectory: {design_dir}")

    if not rtl_dir.exists():
        raise FileNotFoundError(f"Design directory missing 'rtl/' subdirectory: {design_dir}")

    # Find specification file
    # Priority: *spec*.md > specification.md > first .md file
    spec_candidates = list(docs_dir.glob("*spec*.md")) + list(docs_dir.glob("*Spec*.md"))

    if not spec_candidates:
        # Try any .md file
        spec_candidates = list(docs_dir.glob("*.md"))

    if not spec_candidates:
        raise ValueError(f"No specification (.md) file found in {docs_dir}")

    spec_path = spec_candidates[0]
    logger.info(f"  Spec: {spec_path.name}")

    # Find all RTL files
    design_files = list(rtl_dir.glob("*.sv")) + list(rtl_dir.glob("*.v"))

    if not design_files:
        raise ValueError(f"No RTL (.sv/.v) files found in {rtl_dir}")

    # Sort to ensure deterministic ordering
    design_files = sorted(design_files)

    for df in design_files:
        logger.info(f"  Design: {df.name}")

    logger.info(
        f"Auto-discovered {design_dir.name}: "
        f"{len(design_files)} RTL file(s)"
    )

    # In auto-discovery mode, no distinction between design and context
    # All RTL files are treated as design files
    return DesignConfig(
        design_name=design_dir.name,
        spec_path=spec_path,
        design_files=design_files,
        design_context_files=[]
    )
