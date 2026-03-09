#!/usr/bin/env python3
"""
Generate a dashboard.json entry for an OpenTitan design in data/.

Usage:
    python scripts/ot_gen_dashboard_entry.py <design_name> [options]

Examples:
    python scripts/ot_gen_dashboard_entry.py ot_adc
    python scripts/ot_gen_dashboard_entry.py ot_adc --base-dir /path/to/data
    python scripts/ot_gen_dashboard_entry.py ot_adc --print-only

The script:
  1. Finds all *.sv files in <design>/rtl/ and <design>/deps/
  2. Separates *_pkg.sv files from module files
  3. Parses package-to-package references to build a dependency graph
  4. Topologically sorts packages
  5. Identifies the top module (same stem as design name, or largest file)
  6. Emits the JSON fragment, optionally writing it into dashboard.json

Ordering rules (matches what QuestaSim requires):
  - Packages before modules (packages must be compiled in dependency order)
  - design_context: all deps + design's own packages + design's own support modules
  - design: only the top-level design module (e.g. adc_ctrl.sv)
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from collections import defaultdict

# ---------------------------------------------------------------------------
# Package dependency detection
# ---------------------------------------------------------------------------

def find_pkg_deps(pkg_path: Path, all_pkg_stems: set) -> set:
    """
    Return the set of package stems that pkg_path depends on.
    Detects:
      - import <pkg>::*   or   import <pkg>::name
      - <pkg>::<identifier>  (any :: reference)
    """
    text = pkg_path.read_text(errors="replace")
    deps = set()
    for m in re.finditer(r'\b(\w+)::', text):
        name = m.group(1)
        if name in all_pkg_stems and name != pkg_path.stem:
            deps.add(name)
    for m in re.finditer(r'import\s+(\w+)::', text):
        name = m.group(1)
        if name in all_pkg_stems and name != pkg_path.stem:
            deps.add(name)
    return deps


def topological_sort(graph: dict) -> list:
    """
    Kahn's algorithm for topological sort of a dependency graph.
    graph: {node: set_of_deps}
    Returns nodes in an order where all deps come before dependents.
    Raises ValueError on cycles.
    """
    # Build in-degree and reverse adjacency
    in_degree = {n: 0 for n in graph}
    rev = defaultdict(set)
    for node, deps in graph.items():
        for dep in deps:
            if dep in graph:
                in_degree[node] += 1
                rev[dep].add(node)

    queue = sorted(n for n, d in in_degree.items() if d == 0)
    result = []
    while queue:
        node = queue.pop(0)
        result.append(node)
        for dependent in sorted(rev[node]):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)
    if len(result) != len(graph):
        unresolved = set(graph) - set(result)
        raise ValueError(f"Cycle detected among packages: {unresolved}")
    return result


# ---------------------------------------------------------------------------
# Design entry generation
# ---------------------------------------------------------------------------

def find_top_module(rtl_dir: Path, design_name: str) -> Path:
    """
    Find the top-level design file. Prefer exact name match, else largest file.
    design_name is e.g. 'ot_adc' -> look for 'adc_ctrl.sv' or 'adc_ctrl_top.sv'
    """
    sv_files = [f for f in rtl_dir.glob("*.sv") if not f.name.endswith("_pkg.sv")]
    if not sv_files:
        raise ValueError(f"No .sv modules found in {rtl_dir}")

    # Strip ot_ prefix to get the base name (e.g. 'ot_adc' -> 'adc')
    base = design_name.removeprefix("ot_")

    # Prefer exact match: adc_ctrl.sv, aon_timer.sv, lc_ctrl.sv, mbx.sv, rom_ctrl.sv
    for f in sv_files:
        stem = f.stem
        # Match if stem equals base or base_<something> but NOT contains _reg_ or _pkg
        if stem == base or (stem.startswith(base) and "_reg" not in stem
                            and "_fsm" not in stem and "_core" not in stem
                            and "_if" not in stem and "_decode" not in stem
                            and "_transition" not in stem and "_signal" not in stem
                            and "_state" not in stem and "_top" not in stem
                            and "_intr" not in stem and "_mux" not in stem
                            and "_compare" not in stem and "_counter" not in stem
                            and "_sram" not in stem and "_scramble" not in stem
                            and "_imbx" not in stem and "_ombx" not in stem
                            and "_hostif" not in stem and "_sysif" not in stem
                            and "_kmac" not in stem and "_token" not in stem
                            and "_dmi" not in stem):
            return f

    # Fallback: return the largest file (most likely top)
    return max(sv_files, key=lambda f: f.stat().st_size)


def build_entry(design_name: str, data_dir: Path) -> dict:
    design_dir = data_dir / design_name
    rtl_dir = design_dir / "rtl"
    deps_dir = design_dir / "deps"

    if not rtl_dir.exists():
        raise ValueError(f"RTL directory not found: {rtl_dir}")
    if not deps_dir.exists():
        raise ValueError(f"Deps directory not found: {deps_dir}")

    # Collect all pkg files from both locations
    rtl_pkgs  = sorted(rtl_dir.glob("*_pkg.sv"))
    deps_pkgs = sorted(deps_dir.glob("*_pkg.sv"))
    all_pkgs  = deps_pkgs + rtl_pkgs  # deps first so their stems are known

    all_pkg_stems = {p.stem for p in all_pkgs}

    # Build dependency graph for packages
    graph = {}
    path_by_stem = {p.stem: p for p in all_pkgs}
    for pkg in all_pkgs:
        graph[pkg.stem] = find_pkg_deps(pkg, all_pkg_stems)

    # Topological sort
    ordered_stems = topological_sort(graph)

    # Separate rtl vs deps pkg paths (keep original location)
    rtl_pkg_stems  = {p.stem for p in rtl_pkgs}

    # Non-pkg module files
    rtl_modules  = sorted(f for f in rtl_dir.glob("*.sv") if not f.name.endswith("_pkg.sv"))
    deps_modules = sorted(f for f in deps_dir.glob("*.sv") if not f.name.endswith("_pkg.sv"))

    # Identify top module (goes into "design")
    top_file = find_top_module(rtl_dir, design_name)
    rtl_non_top_modules = [f for f in rtl_modules if f != top_file]

    # Build ordered file lists using $(BASE_DIR) placeholder
    def rel(p: Path) -> str:
        # Path relative to data_dir parent (i.e. data/<design>/...)
        rel_path = p.relative_to(data_dir.parent)
        return f"$(BASE_DIR)/{'/'.join(rel_path.parts[1:])}"

    # design_context: ordered pkgs (deps first, then rtl pkgs), then modules
    context_files = []

    # 1. Packages in topological order
    for stem in ordered_stems:
        context_files.append(rel(path_by_stem[stem]))

    # 2. Non-pkg include/macro files (prim_assert.sv, prim_flop_macros.sv)
    for f in deps_modules:
        if f.stem in ("prim_assert", "prim_flop_macros"):
            context_files.append(rel(f))

    # 3. All other dep modules (alphabetical, skip the two already added)
    special = {"prim_assert", "prim_flop_macros"}
    for f in deps_modules:
        if f.stem not in special:
            context_files.append(rel(f))

    # 4. RTL support modules (not the top)
    for f in rtl_non_top_modules:
        context_files.append(rel(f))

    # Find spec files
    docs_dir = design_dir / "docs"
    spec_files = []
    if docs_dir.exists():
        for ext in ("*.md",):
            spec_files.extend(sorted(docs_dir.glob(ext)))
    spec_list = [rel(f) for f in spec_files]

    entry = {
        "design": [rel(top_file)],
        "design_context": context_files,
    }
    if spec_list:
        entry["spec"] = spec_list

    return entry


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate dashboard.json entry for an OT design.")
    parser.add_argument("design_name", help="Design name (e.g. ot_adc)")
    parser.add_argument("--base-dir", default=None,
                        help="Path to the data/ directory (default: <project_root>/data)")
    parser.add_argument("--dashboard", default=None,
                        help="Path to dashboard.json to write the entry into")
    parser.add_argument("--print-only", action="store_true",
                        help="Just print the JSON fragment, do not modify dashboard.json")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    data_dir = Path(args.base_dir) if args.base_dir else project_root / "data"
    dashboard_path = Path(args.dashboard) if args.dashboard else project_root / "dashboard.json"

    print(f"Building entry for: {args.design_name}", file=sys.stderr)
    entry = build_entry(args.design_name, data_dir)

    fragment = json.dumps({args.design_name: entry}, indent=4)

    if args.print_only:
        print(fragment)
        return

    # Write into dashboard.json
    with open(dashboard_path) as f:
        dashboard = json.load(f)

    if args.design_name in dashboard:
        print(f"  Overwriting existing entry for '{args.design_name}'", file=sys.stderr)
    else:
        print(f"  Adding new entry for '{args.design_name}'", file=sys.stderr)

    dashboard[args.design_name] = entry

    with open(dashboard_path, "w") as f:
        json.dump(dashboard, f, indent=4)
        f.write("\n")

    print(f"  Written to {dashboard_path}", file=sys.stderr)

    # Summary
    n_pkg = sum(1 for p in entry["design_context"] if "_pkg" in p)
    n_mod = len(entry["design_context"]) - n_pkg
    print(f"  design      : {entry['design'][0]}", file=sys.stderr)
    print(f"  context pkgs: {n_pkg}", file=sys.stderr)
    print(f"  context mods: {n_mod}", file=sys.stderr)


if __name__ == "__main__":
    main()
