"""Pre-compile and post-compile validation for UVM-generated files.

Pre-compile checks are pure regex — zero tokens, zero compilation cost.
They catch the most common LLM mistakes and return targeted fix instructions
so the LLM can correct the code without wasting a compile cycle.

Post-compile checks verify UVM version and catch errors that only manifest
after compilation (e.g., dual-UVM conflicts).
"""

import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Pre-compile validation ────────────────────────────────────────────────────

def validate_uvm_files(
    work_dir: Path,
    sequence_file: str,
    test_name: str,
    interface_name: Optional[str] = None,
    env_class: Optional[str] = None,
    top_module: Optional[str] = None,
) -> Tuple[bool, List[str]]:
    """Run static checks on LLM-generated UVM files before compilation.

    Args:
        work_dir: Working directory containing testbenches/
        sequence_file: Filename of the sequence file (e.g., "alu_core_seq.sv")
        test_name: Expected UVM test class name (e.g., "alu_core_cov_test")
        interface_name: Expected interface name (e.g., "alu_core_if")
        env_class: Expected env class name (e.g., "alu_core_env")
        top_module: Expected top module name (e.g., "alu_core_Top")

    Returns:
        (passed, errors) — passed is True if all checks pass;
        errors is a list of human-readable fix instructions.
    """
    errors: List[str] = []

    seq_path = work_dir / "testbenches" / sequence_file
    # Test file lives alongside the seq file
    test_file = sequence_file.replace("_seq.sv", "_test.sv")
    test_path = work_dir / "testbenches" / test_file

    # ── Check 1: Files exist ──────────────────────────────────────────────
    if not seq_path.exists():
        errors.append(f"Sequence file missing: {sequence_file}. Generate it before compiling.")
        return False, errors  # Can't do further checks

    # ── Read file contents ────────────────────────────────────────────────
    seq_content = seq_path.read_text(errors='ignore')
    test_content = test_path.read_text(errors='ignore') if test_path.exists() else ""

    all_content = seq_content + "\n" + test_content

    # ── Check 2: UVM imports present ──────────────────────────────────────
    if not re.search(r'import\s+uvm_pkg\s*::\s*\*', all_content):
        errors.append(
            "Missing `import uvm_pkg::*;` — add it at the top of the sequence file. "
            "This is required for UVM macros and base classes."
        )

    if not re.search(r'`include\s+"uvm_macros\.svh"', all_content):
        errors.append(
            'Missing `include "uvm_macros.svh"` — add it after the uvm_pkg import.'
        )

    # ── Check 3: Test class name matches config ───────────────────────────
    if test_name and test_content:
        # Look for the class declaration that extends uvm_test
        test_class_match = re.search(
            r'class\s+(\w+)\s+extends\s+uvm_test', test_content
        )
        if test_class_match:
            declared_name = test_class_match.group(1)
            if declared_name != test_name:
                errors.append(
                    f"Test class name mismatch: declared `{declared_name}` but "
                    f"config expects `{test_name}`. Rename the class to `{test_name}` "
                    f"or the +UVM_TESTNAME will cause INVTST at simulation."
                )
        elif test_content.strip():
            # Test file exists but no uvm_test class found
            errors.append(
                f"No class extending uvm_test found in {test_file}. "
                f"Declare `class {test_name} extends uvm_test;` with "
                f"`uvm_component_utils({test_name})`."
            )

    # ── Check 4: Factory registration macros ──────────────────────────────
    # Every class extending a UVM base needs `uvm_*_utils
    uvm_classes = re.findall(
        r'class\s+(\w+)\s+extends\s+uvm_\w+', all_content
    )
    for cls in uvm_classes:
        # Check for uvm_component_utils or uvm_object_utils (with or without _begin)
        pattern = rf'`uvm_(?:component|object)_utils(?:_begin)?\s*\(\s*{re.escape(cls)}\s*\)'
        if not re.search(pattern, all_content):
            errors.append(
                f"Class `{cls}` extends a UVM base but is missing factory registration. "
                f"Add `uvm_component_utils({cls})` or `uvm_object_utils({cls})` inside the class."
            )

    # ── Check 5: Interface name consistency ───────────────────────────────
    if interface_name and all_content:
        # Check that generated code uses the correct interface name
        # Look for virtual interface declarations with wrong names
        vif_decls = re.findall(r'virtual\s+(\w+)\s+\w+', all_content)
        for vif_name in vif_decls:
            # Skip UVM base types and common SV types
            if vif_name in ('class', 'function', 'task', 'protected', 'local'):
                continue
            if vif_name.endswith('_if') and vif_name != interface_name:
                errors.append(
                    f"Wrong interface name: found `virtual {vif_name}` but the design "
                    f"uses `{interface_name}`. Replace all occurrences of `{vif_name}` "
                    f"with `{interface_name}`."
                )
                break  # One error is enough

    # ── Check 6: config_db get/set use correct interface ──────────────────
    if interface_name and all_content:
        config_db_matches = re.findall(
            r'uvm_config_db\s*#\s*\(\s*virtual\s+(\w+)\s*\)', all_content
        )
        for cdb_if in config_db_matches:
            if cdb_if != interface_name:
                errors.append(
                    f"config_db uses wrong interface: `uvm_config_db#(virtual {cdb_if})` "
                    f"should be `uvm_config_db#(virtual {interface_name})`."
                )
                break

    # ── Check 7: Basic syntax — unmatched begin/end, class/endclass ───────
    _check_balanced_keywords(seq_content, "sequence file", errors)
    if test_content:
        _check_balanced_keywords(test_content, "test file", errors)

    # ── Check 8: Sequence body_type matches seq_item class ────────────────
    # Sequences must use `uvm_sequence#(correct_item)` or body will fail
    seq_item_classes = re.findall(
        r'class\s+(\w+)\s+extends\s+uvm_sequence_item', all_content
    )
    if seq_item_classes:
        expected_item = seq_item_classes[0]
        seq_decls = re.findall(
            r'class\s+\w+\s+extends\s+uvm_sequence\s*#\s*\(\s*(\w+)\s*\)', all_content
        )
        for item_type in seq_decls:
            if item_type != expected_item:
                errors.append(
                    f"Sequence parameterized with `{item_type}` but seq_item class "
                    f"is `{expected_item}`. Use `uvm_sequence#({expected_item})`."
                )
                break

    passed = len(errors) == 0
    if passed:
        logger.info("UVM pre-compile validation: PASSED")
    else:
        logger.warning(f"UVM pre-compile validation: FAILED ({len(errors)} issues)")
        for i, err in enumerate(errors, 1):
            logger.warning(f"  [{i}] {err}")

    return passed, errors


def _check_balanced_keywords(content: str, label: str, errors: List[str]):
    """Check for obviously unbalanced begin/end, class/endclass, etc."""
    pairs = [
        ("class", "endclass"),
        ("module", "endmodule"),
        ("function", "endfunction"),
        ("task", "endtask"),
    ]

    # Strip comments and strings to avoid false positives
    stripped = _strip_comments(content)

    for opener, closer in pairs:
        open_count = len(re.findall(rf'\b{opener}\b', stripped))
        close_count = len(re.findall(rf'\b{closer}\b', stripped))
        if open_count != close_count:
            errors.append(
                f"Unbalanced `{opener}`/`{closer}` in {label}: "
                f"{open_count} openers vs {close_count} closers. "
                f"Check for missing `{closer};` statements."
            )


def _strip_comments(content: str) -> str:
    """Remove // and /* */ comments from SV code."""
    # Remove block comments
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    # Remove line comments
    content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
    return content


# ── Post-compile verification ─────────────────────────────────────────────────

def verify_compile_log(
    stdout: str,
    stderr: str = "",
) -> Tuple[bool, List[str]]:
    """Verify compilation output for UVM-specific issues.

    Run this AFTER a successful compilation (return code 0) to catch
    issues that don't cause compilation failure but will break simulation.

    Args:
        stdout: Compilation stdout
        stderr: Compilation stderr

    Returns:
        (passed, warnings) — passed is True if no blocking issues found;
        warnings is a list of issues that may cause simulation failure.
    """
    warnings: List[str] = []
    combined = stdout + "\n" + stderr

    # ── Check 1: Verify UVM 1.2 was used (not 1.1d) ──────────────────────
    uvm_versions = re.findall(r'uvm_pkg\s*\((uvm-[\d.]+\w*)', combined)
    for ver in uvm_versions:
        if "1.1" in ver:
            warnings.append(
                f"UVM version conflict: loaded {ver} instead of 1.2. "
                f"The vmap mtiUvm step may have failed. Check that "
                f"`vmap mtiUvm uvm_lib` ran successfully."
            )

    # ── Check 2: Check for dual-UVM loading ───────────────────────────────
    # If both mtiUvm and uvm_lib packages appear, we have a conflict
    has_mtiUvm = 'mtiUvm.uvm_pkg' in combined
    has_uvm_lib = 'uvm_lib.uvm_pkg' in combined
    if has_mtiUvm and has_uvm_lib:
        warnings.append(
            "Dual-UVM conflict detected: both mtiUvm (1.1d) and uvm_lib (1.2) "
            "were loaded. This will cause INVTST factory errors at simulation. "
            "Ensure `vmap mtiUvm uvm_lib` is executed before design compilation."
        )

    # ── Check 3: Check for vlog errors that were somehow missed ───────────
    error_count = re.findall(r'Errors:\s*(\d+)', combined)
    for count_str in error_count:
        if int(count_str) > 0:
            warnings.append(
                f"Compilation reported {count_str} error(s) but may have returned "
                f"success. Review the compile log for error details."
            )

    # ── Check 4: vsim-12460 / vsim-8754 stale binary warnings ────────────
    if 'vsim-12460' in combined or 'vsim-8754' in combined:
        warnings.append(
            "Stale UVM binary detected (vsim-12460/vsim-8754). The pre-compiled "
            "UVM library is incompatible with this QuestaSim version. Ensure "
            "UVM is compiled from source into uvm_lib."
        )

    passed = len(warnings) == 0
    if passed:
        logger.info("UVM post-compile verification: PASSED")
    else:
        logger.warning(f"UVM post-compile verification: {len(warnings)} issue(s)")
        for i, w in enumerate(warnings, 1):
            logger.warning(f"  [{i}] {w}")

    return passed, warnings
