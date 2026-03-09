#!/usr/bin/env python3
"""
Scaffold compile-and-simulate test for any design in dashboard.json.

Usage:
    python scripts/test_design.py <design_name> [options]

Examples:
    python scripts/test_design.py chacha_top
    python scripts/test_design.py ot_dma
    python scripts/test_design.py ot_dma --compiler /tools/questa/bin

Reads COMPILER, DASHBOARD_PATH, and BASE_DIR from .env if present.
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from dotenv import load_dotenv

load_dotenv()


def _resolve_variables(s: str, variables: dict) -> str:
    for k, v in variables.items():
        s = s.replace(f"$({k})", v)
    return s


def load_design_for_test(dashboard_path: Path, design_name: str, base_dir: Path):
    """
    Lightweight design loader for compile/sim testing.
    Unlike get_design_from_dashboard, does NOT require a spec field,
    so it works for designs that don't yet have documentation.
    Returns (design_files, design_context_files).
    """
    with open(dashboard_path) as f:
        dashboard = json.load(f)

    if design_name not in dashboard:
        raise ValueError(f"Design '{design_name}' not found in {dashboard_path}")

    entry = dashboard[design_name]
    variables = {"BASE_DIR": str(base_dir)}

    def resolve_list(key):
        files = []
        for raw in entry.get(key, []):
            if not isinstance(raw, str):
                continue
            p = Path(_resolve_variables(raw, variables))
            if p.exists():
                files.append(p)
            else:
                logging.warning(f"File not found (skipping): {p}")
        return files

    design_files = resolve_list("design")
    context_files = resolve_list("design_context")
    compile_deps_files = resolve_list("compile_deps")

    if not design_files:
        raise ValueError(f"Design '{design_name}' has no valid 'design' files")

    return design_files, context_files, compile_deps_files

# ---------------------------------------------------------------------------
# Scaffold testbench  instantiates the top module with all ports tied off
# ---------------------------------------------------------------------------
SCAFFOLD_TB = """\
// Auto-generated scaffold testbench for compile/sim sanity check.
// Not a functional testbench  only verifies elaboration succeeds.
`timescale 1ns/1ps
module tb_llm;
  logic clk;
  initial begin clk = 0; forever #5 clk = ~clk; end
  initial begin
    #100;
    $display("SCAFFOLD PASS: design elaborated and simulated successfully.");
    $finish;
  end
  // DUT instantiated with wildcard port connection (.*)
  // QuestaSim will warn about unconnected ports  that is expected.
  {top_module} u_dut (.*);
endmodule
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(cmd: list, cwd: Path, label: str) -> tuple[bool, str, str]:
    """Run a subprocess, return (success, stdout, stderr)."""
    logging.info(f"[{label}] {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd))
    return result.returncode == 0, result.stdout, result.stderr


def check_questa_errors(stdout: str) -> bool:
    """Return True if QuestaSim reports Errors: 0."""
    for line in reversed(stdout.splitlines()):
        line = line.strip().lstrip("#").strip()
        if line.startswith("Errors:"):
            parts = line.split(",")
            err_part = parts[0].split(":")
            try:
                return int(err_part[1].strip()) == 0
            except (IndexError, ValueError):
                return False
    return False


def top_module_name(design_files) -> str:
    """Return the stem of the first design file as the assumed top module name."""
    return Path(design_files[0]).stem


def collect_incdirs(all_files: list) -> list:
    """Collect unique parent directories to use as +incdir+ for .svh resolution."""
    dirs = set()
    for f in all_files:
        dirs.add(str(Path(f).parent))
    return sorted(dirs)


def split_vlog_commands(questa_bin: Path, all_files: list, tb: Path) -> list:
    """
    Mirror build_vlog_commands(): separate .v (no -sv) and .sv (with -sv).
    No coverage flags  this is a plain compile check.
    """
    vlog = str(questa_bin / "vlog")
    files_with_tb = [str(tb)] + [str(f) for f in all_files]
    incdirs = [f"+incdir+{d}" for d in collect_incdirs(files_with_tb)]

    v_files  = [f for f in files_with_tb if f.endswith(".v")]
    sv_files = [f for f in files_with_tb if not f.endswith(".v")]

    commands = []
    if v_files:
        commands.append([vlog] + incdirs + v_files)
    if sv_files:
        commands.append([vlog, "-sv"] + incdirs + sv_files)
    return commands


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scaffold compile+sim test for a dashboard design.")
    parser.add_argument("design_name", help="Design name as it appears in dashboard.json")
    parser.add_argument("--dashboard", default=os.getenv("DASHBOARD_PATH"),
                        help="Path to dashboard.json (or set DASHBOARD_PATH in .env)")
    parser.add_argument("--base-dir", default=os.getenv("BASE_DIR"),
                        help="Base data directory (or set BASE_DIR in .env)")
    parser.add_argument("--compiler", default=os.getenv("COMPILER"),
                        help="Path to QuestaSim bin/ directory (or set COMPILER in .env)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s"
    )

    # --- Resolve paths ---
    project_root = Path(__file__).parent.parent

    dashboard_path = Path(args.dashboard) if args.dashboard else project_root / "dashboard.json"
    if not dashboard_path.exists():
        logging.error(f"dashboard.json not found: {dashboard_path}")
        sys.exit(1)

    base_dir = Path(args.base_dir) if args.base_dir else project_root / "data"

    if not args.compiler:
        logging.error("QuestaSim bin path required. Set COMPILER in .env or pass --compiler.")
        sys.exit(1)
    questa_bin = Path(args.compiler)

    # --- Load design from dashboard ---
    logging.info(f"Loading design: {args.design_name}")
    try:
        design_files, context_files, compile_deps_files = load_design_for_test(dashboard_path, args.design_name, base_dir)
    except (FileNotFoundError, ValueError) as e:
        logging.error(str(e))
        sys.exit(1)

    # compile_deps first (no coverage), then context, then design (ordering matters)
    all_design_files = compile_deps_files + context_files + design_files
    top_module = top_module_name(design_files)
    logging.info(f"Top module     : {top_module}")
    logging.info(f"Design files   : {len(design_files)}")
    logging.info(f"Context files  : {len(context_files)}")
    logging.info(f"Compile deps   : {len(compile_deps_files)}")
    logging.info(f"Total files    : {len(all_design_files)}")

    # --- Create temp work directory ---
    work_dir = Path(tempfile.mkdtemp(prefix=f"test_{args.design_name}_"))
    logging.info(f"Work dir     : {work_dir}")

    try:
        # --- Write scaffold testbench ---
        tb_path = work_dir / "tb_scaffold.sv"
        tb_path.write_text(SCAFFOLD_TB.format(top_module=top_module))

        # --- Create work library ---
        ok, stdout, stderr = run([str(questa_bin / "vlib"), "work"], work_dir, "vlib")
        if not ok:
            logging.error(f"vlib failed:\n{stderr}")
            sys.exit(1)

        # --- Compile ---
        print(f"\n{'='*60}")
        print(f"  COMPILING: {args.design_name}")
        print(f"{'='*60}")

        compile_commands = split_vlog_commands(questa_bin, all_design_files, tb_path)
        compile_ok = True
        for i, cmd in enumerate(compile_commands):
            label = f"vlog pass {i+1}/{len(compile_commands)}"
            ok, stdout, stderr = run(cmd, work_dir, label)
            print(stdout)
            if stderr:
                print(stderr, file=sys.stderr)
            if not check_questa_errors(stdout):
                compile_ok = False
                break

        if not compile_ok:
            print("\n[RESULT] COMPILE FAILED")
            sys.exit(1)

        print("\n[RESULT] COMPILE OK")

        # --- Simulate ---
        print(f"\n{'='*60}")
        print(f"  SIMULATING: {args.design_name}")
        print(f"{'='*60}")

        vsim_cmd = [
            str(questa_bin / "vsim"),
            "work.tb_llm",
            "-c",
            "-suppress", "vsim-3009",   # timeunit/timeprecision mismatch
            "-suppress", "vsim-3999",   # enum-to-logic port type mismatch
            "-suppress", "vopt-2247",   # wildcard port connection unmatched
            "-do", "run -all; exit"
        ]
        ok, stdout, stderr = run(vsim_cmd, work_dir, "vsim")
        print(stdout)
        if stderr:
            print(stderr, file=sys.stderr)

        # Check for $finish or PASS in output  scaffold always calls $finish
        sim_ok = "$finish" in stdout or "SCAFFOLD PASS" in stdout
        if not sim_ok and not ok:
            print("\n[RESULT] SIMULATION FAILED")
            sys.exit(1)

        print("\n[RESULT] SIMULATION OK")
        print(f"\n{'='*60}")
        print(f"  DESIGN '{args.design_name}' IS READY FOR FRAMEWORK INGESTION")
        print(f"{'='*60}\n")

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
