"""Shared UVM helper functions used by all three graph architectures (V1, V2, V2.1)."""

import shutil
import logging
import re as _re
from pathlib import Path

from ..config import Config


def prepare_uvm_workdir(config: Config) -> None:
    """Prepare the work directory for UVM compilation.

    1. Copy the .f file to work_dir, rewriting relative paths to absolute.
    2. Replace the sequence file, test file, and driver file entries so they
       point to work_dir/testbenches/ where the LLM will generate/modify them.
    3. Auto-detect the driver file and copy original to work_dir/testbenches/.
    4. Create work_dir/testbenches/ and work_dir/iterations/.
    """
    work_dir = config.work_dir
    original_filelist = config.uvm_filelist

    # The .f file's relative paths are relative to the sim/ directory,
    # which is a sibling of the testbench/ directory.
    sim_dir = (
        config.uvm_testbench_dir.parent / "sim"
        if config.uvm_testbench_dir
        else original_filelist.parent.parent / "sim"
    )

    # Auto-detect the driver file from the testbench directory
    driver_file = None
    if config.uvm_testbench_dir and config.uvm_testbench_dir.exists():
        for f in config.uvm_testbench_dir.iterdir():
            if f.suffix == '.sv':
                try:
                    content = f.read_text()
                    if _re.search(r'extends\s+uvm_driver', content):
                        driver_file = f
                        logging.info(f"UVM driver auto-detected: {f.name}")
                        break
                except Exception:
                    pass

    if driver_file:
        config.uvm_driver_file = driver_file
    else:
        logging.warning("Could not auto-detect UVM driver file")

    # Read original .f file
    with open(original_filelist, 'r') as f:
        lines = f.readlines()

    # Rewrite paths to absolute, replacing sequence, test, and driver entries
    new_lines = []
    seq_file = config.uvm_sequence_file           # e.g., "alu_core_seq.sv"
    test_file = f"{config.uvm_test_name}.sv"      # e.g., "alu_core_test.sv"
    driver_filename = driver_file.name if driver_file else None

    testbenches_dir = work_dir / "testbenches"
    testbenches_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "iterations").mkdir(parents=True, exist_ok=True)

    # Build lookup tables for fallback resolution
    # Design files by basename (for RTL fallback)
    design_files_by_name: dict[str, Path] = {}
    for df in (config.design_files or []):
        p = Path(df)
        design_files_by_name[p.name] = p
    for df in (config.design_context_files or []):
        p = Path(df)
        design_files_by_name[p.name] = p

    # UVM testbench files by basename (for infra fallback)
    uvm_tb_files_by_name: dict[str, Path] = {}
    if config.uvm_testbench_dir and config.uvm_testbench_dir.exists():
        for f in config.uvm_testbench_dir.iterdir():
            if f.suffix in ('.sv', '.v'):
                uvm_tb_files_by_name[f.name] = f

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("#"):
            new_lines.append(line)
            continue

        # Skip compiler directives and env-var lines — handled separately by
        # the UVM compilation step (vlog already gets +incdir+$UVM_HOME/src
        # and uvm_pkg.sv via explicit flags).
        if stripped.startswith("+") or "$" in stripped:
            logging.info(f"UVM .f file: skipping compiler directive: {stripped}")
            continue

        # Resolve the relative path against sim_dir
        resolved = (sim_dir / stripped).resolve()
        filename = resolved.name

        # Redirect sequence file, test file, and driver to work_dir/testbenches/
        if filename == seq_file:
            new_lines.append(str(testbenches_dir / seq_file) + "\n")
            logging.info(f"UVM .f file: redirecting {filename} → {testbenches_dir / seq_file}")
        elif filename == test_file:
            new_lines.append(str(testbenches_dir / test_file) + "\n")
            logging.info(f"UVM .f file: redirecting {filename} → {testbenches_dir / test_file}")
        elif driver_filename and filename == driver_filename:
            dest = testbenches_dir / driver_filename
            new_lines.append(str(dest) + "\n")
            logging.info(f"UVM .f file: redirecting driver {filename} → {dest}")
        elif resolved.exists():
            new_lines.append(str(resolved) + "\n")
        else:
            # Resolved path doesn't exist — try fallbacks by filename
            if filename in design_files_by_name:
                fallback = design_files_by_name[filename]
                new_lines.append(str(fallback) + "\n")
                logging.info(f"UVM .f file: resolved via design files: {filename} → {fallback}")
            elif filename in uvm_tb_files_by_name:
                fallback = uvm_tb_files_by_name[filename]
                new_lines.append(str(fallback) + "\n")
                logging.info(f"UVM .f file: resolved via UVM dir: {filename} → {fallback}")
            else:
                # Keep the broken path so the compiler reports a clear error
                new_lines.append(str(resolved) + "\n")
                logging.warning(f"UVM .f file: could not resolve '{stripped}' (tried {resolved})")

    # Copy original driver to work_dir/testbenches/ (unmodified starting point)
    if driver_file:
        dest_driver = testbenches_dir / driver_file.name
        shutil.copy2(driver_file, dest_driver)
        logging.info(f"UVM driver copied to work_dir: {dest_driver}")

    # Write the modified .f file to work_dir
    work_filelist = work_dir / "filelist.f"
    with open(work_filelist, 'w') as f:
        f.writelines(new_lines)

    # Update config to use the new filelist
    config.uvm_filelist = work_filelist
    logging.info(f"UVM filelist prepared: {work_filelist}")


def build_uvm_prompt_context(config: Config) -> dict:
    """Read UVM context files and build kwargs for prompt loader functions."""
    # Read seq_item content
    seq_item_content = ""
    if config.uvm_seq_item_file and config.uvm_seq_item_file.exists():
        with open(config.uvm_seq_item_file, 'r') as f:
            seq_item_content = f.read()

    # Read coverage module content
    cov_module_content = ""
    if config.uvm_coverage_module_file and config.uvm_coverage_module_file.exists():
        with open(config.uvm_coverage_module_file, 'r') as f:
            cov_module_content = f.read()

    # List UVM testbench files and extract interface/env class names
    uvm_tb_files = []
    uvm_interface_name = None
    uvm_env_class = None
    if config.uvm_testbench_dir and config.uvm_testbench_dir.exists():
        for f in sorted(config.uvm_testbench_dir.iterdir()):
            if f.suffix == '.sv' and f.name != config.uvm_sequence_file and \
               f.name != f"{config.uvm_test_name}.sv":
                uvm_tb_files.append(str(f))
                try:
                    content = f.read_text()
                    if not uvm_interface_name:
                        m = _re.search(r'^interface\s+(\w+)', content, _re.MULTILINE)
                        if m:
                            uvm_interface_name = m.group(1)
                    if not uvm_env_class:
                        m = _re.search(r'class\s+(\w+)\s+extends\s+uvm_env', content)
                        if m:
                            uvm_env_class = m.group(1)
                except Exception:
                    pass

    if uvm_interface_name:
        logging.info(f"UVM interface name detected: {uvm_interface_name}")
    if uvm_env_class:
        logging.info(f"UVM env class detected: {uvm_env_class}")

    return {
        'uvm_enabled': True,
        'uvm_seq_item_content': seq_item_content,
        'uvm_coverage_module_content': cov_module_content,
        'uvm_sequence_file': config.uvm_sequence_file,
        'uvm_test_name': config.uvm_test_name,
        'uvm_testbench_files': uvm_tb_files,
        'uvm_interface_name': uvm_interface_name,
        'uvm_env_class': uvm_env_class,
        'uvm_coverage_mode': config.uvm_coverage_mode,
    }
