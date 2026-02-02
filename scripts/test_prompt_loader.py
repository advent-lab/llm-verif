#!/usr/bin/env python3
"""Comprehensive test for system prompt loading pipeline.

Tests the complete flow:
1. Load design from dashboard.json (or auto-discover from directory)
2. Extract module headers from RTL files
3. Generate system prompt with all variables interpolated

Usage:
  Edit the configuration variables below to test different designs and settings.
  
  USE_DASHBOARD=True:  Load from dashboard.json (recommended)
  USE_DASHBOARD=False: Auto-discover from directory structure

"""

import sys
from pathlib import Path

# Add parent directory to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.prompts.loader import load_system_prompt
from src.utils.dashboard_loader import get_design_from_dashboard, auto_discover_design
from src.utils.design_loader import extract_all_module_headers

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# =============================================================================
# CONFIGURATION - Modify these to test different scenarios
# =============================================================================

# Method 1: Load from dashboard.json (recommended)
USE_DASHBOARD = True
DASHBOARD_PATH = project_root / "dashboard.json"
DESIGN_NAME = "cvdp_agentic_spi_complex_mult"  # Change to any design in dashboard.json

# Method 2: Auto-discover from directory (fallback)
AUTO_DISCOVER_DIR = project_root / "data" / "cvdp_agentic_alu"  # Used if USE_DASHBOARD=False
# Feature toggles
DESIGN_CONTEXT_ENABLED = True
TESTPLAN_ENABLED = True

# Iteration parameters
MAX_ITERATIONS = 10
SIM_RUNS = 5

# =============================================================================
# LOAD DESIGN CONFIGURATION
# =============================================================================

if USE_DASHBOARD:
    print(f"Loading design '{DESIGN_NAME}' from dashboard...")
    config = get_design_from_dashboard(
        dashboard_path=DASHBOARD_PATH,
        design_name=DESIGN_NAME,
        base_dir=project_root / "data"
    )
else:
    print(f"Auto-discovering design in '{AUTO_DISCOVER_DIR}'...")
    config = auto_discover_design(AUTO_DISCOVER_DIR)

print(f"  Design: {config.design_name}")
print(f"  Spec: {config.spec_path}")
print(f"  Design files: {len(config.design_files)}")
for df in config.design_files:
    print(f"    - {df}")
print(f"  Context files: {len(config.design_context_files)}")
for cf in config.design_context_files:
    print(f"    - {cf}")

# =============================================================================
# EXTRACT MODULE HEADERS
# =============================================================================

print(f"\nExtracting module headers...")
module_header = extract_all_module_headers(config.design_files)
print(f"  Extracted {len(module_header)} characters")

# =============================================================================
# GENERATE SYSTEM PROMPT
# =============================================================================

print(f"\nGenerating system prompt...")

# Prepare paths for prompt loader
design_dir = config.design_files[0].parent.parent  # Go up from rtl/ to design root
rtl_dir = config.design_files[0].parent
rtl_files = [f.name for f in config.design_files]
work_dir = project_root / "test_output" / config.design_name

prompt = load_system_prompt(
    design_name=config.design_name,
    design_dir=design_dir,
    spec_path=config.spec_path,
    rtl_dir=rtl_dir,
    rtl_files=rtl_files,
    module_header=module_header,
    design_context_enabled=DESIGN_CONTEXT_ENABLED,
    testplan_enabled=TESTPLAN_ENABLED,
    max_iterations=MAX_ITERATIONS,
    sim_runs=SIM_RUNS
)

print(f"  Generated {len(prompt)} characters (~{len(prompt)//4} tokens)")
print(f"\n{'='*80}")
print("GENERATED SYSTEM PROMPT")
print('='*80)
print(prompt)
