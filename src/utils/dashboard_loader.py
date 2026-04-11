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
        # UVM fields (optional)
        uvm_testbench_dir: Optional[Path] = None,
        uvm_filelist: Optional[Path] = None,
        uvm_sequence_file: Optional[str] = None,
        uvm_top_module: Optional[str] = None,
        uvm_test_name: Optional[str] = None,
        uvm_seq_item_file: Optional[Path] = None,
        uvm_coverage_module_file: Optional[Path] = None,
    ):
        self.design_name = design_name
        self.spec_path = spec_path
        self.design_files = design_files
        self.design_context_files = design_context_files
        # UVM
        self.uvm_testbench_dir = uvm_testbench_dir
        self.uvm_filelist = uvm_filelist
        self.uvm_sequence_file = uvm_sequence_file
        self.uvm_top_module = uvm_top_module
        self.uvm_test_name = uvm_test_name
        self.uvm_seq_item_file = uvm_seq_item_file
        self.uvm_coverage_module_file = uvm_coverage_module_file

    def __repr__(self):
        uvm_str = ", uvm=True" if self.uvm_filelist else ""
        return (
            f"DesignConfig(name={self.design_name}, "
            f"spec={self.spec_path.name}, "
            f"design_files={len(self.design_files)}, "
            f"context_files={len(self.design_context_files)}{uvm_str})"
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

    # ── UVM fields (optional) ────────────────────────────────────────────
    uvm_testbench_dir = None
    uvm_filelist = None
    uvm_sequence_file = None
    uvm_top_module = None
    uvm_test_name = None
    uvm_seq_item_file = None
    uvm_coverage_module_file = None

    if "uvm_testbench_dir" in design_entry:
        uvm_tb_str = _resolve_variables(design_entry["uvm_testbench_dir"], variables)
        uvm_testbench_dir = Path(uvm_tb_str)
        if not uvm_testbench_dir.exists():
            logger.warning(f"UVM testbench dir not found: {uvm_testbench_dir}")

    if "uvm_filelist" in design_entry:
        uvm_fl_str = _resolve_variables(design_entry["uvm_filelist"], variables)
        uvm_filelist = Path(uvm_fl_str)
        if not uvm_filelist.exists():
            logger.warning(f"UVM filelist not found: {uvm_filelist}")

    uvm_sequence_file = design_entry.get("uvm_sequence_file")
    uvm_top_module = design_entry.get("uvm_top_module")
    uvm_test_name = design_entry.get("uvm_test_name")

    if "uvm_seq_item_file" in design_entry:
        uvm_si_str = _resolve_variables(design_entry["uvm_seq_item_file"], variables)
        uvm_seq_item_file = Path(uvm_si_str)

    if "uvm_coverage_module_file" in design_entry:
        uvm_cm_str = _resolve_variables(design_entry["uvm_coverage_module_file"], variables)
        uvm_coverage_module_file = Path(uvm_cm_str)

    if uvm_filelist:
        logger.info(f"  UVM: filelist={uvm_filelist.name}, top={uvm_top_module}, test={uvm_test_name}")

    # ── Log summary ───────────────────────────────────────────────────────
    logger.info(
        f"Loaded {design_name}: "
        f"{len(design_files)} design file(s), "
        f"{len(design_context_files)} context file(s)"
    )

    return DesignConfig(
        design_name=design_name,
        spec_path=spec_path,
        design_files=design_files,
        design_context_files=design_context_files,
        uvm_testbench_dir=uvm_testbench_dir,
        uvm_filelist=uvm_filelist,
        uvm_sequence_file=uvm_sequence_file,
        uvm_top_module=uvm_top_module,
        uvm_test_name=uvm_test_name,
        uvm_seq_item_file=uvm_seq_item_file,
        uvm_coverage_module_file=uvm_coverage_module_file,
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
