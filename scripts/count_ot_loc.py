#!/usr/bin/env python3
"""
Count LOC for every IP design in opentitan/hw/ip/.

Works directly on the opentitan source tree — no copying to data/ or
dashboard.json entries required.

Resolves ALL transitive dependencies (packages AND modules) needed to
compile and simulate each design, giving a total LOC that approximates
the full executed code footprint.

Usage:
    python scripts/count_ot_loc.py
    python scripts/count_ot_loc.py --design adc_ctrl
    python scripts/count_ot_loc.py --verbose
    python scripts/count_ot_loc.py --sort-by total
    python scripts/count_ot_loc.py --ot-dir /path/to/opentitan

LOC categories per design:
  own_rtl  : lines in the design's own hw/ip/<name>/rtl/*.sv
  pkg_deps : lines in transitively-resolved *_pkg.sv from OTHER ip folders
  mod_deps : lines in transitively-resolved non-pkg module files (prim_flop.sv etc.)
  total    : own_rtl + pkg_deps + mod_deps
"""

import argparse
import re
import sys
from collections import deque
from pathlib import Path

# ---------------------------------------------------------------------------
# Infra folders excluded from the "designs" list (still counted as deps).
# ---------------------------------------------------------------------------
INFRA_EXCLUDES = {
    "prim", "prim_generic", "prim_asap7",
    "prim_xilinx", "prim_xilinx_ultrascale",
    "tlul",
}

# Priority ordering when multiple folders define the same file stem.
# Lower index = higher priority.  prim_generic has simulation-safe generics.
INDEX_PRIORITY = [
    "prim_generic",   # highest: generic sim-safe implementations
    "prim",           # standard prim packages/modules
    "tlul",           # bus infrastructure
    # everything else is lower priority (design-specific files)
]


# ---------------------------------------------------------------------------
# LOC counting — identical logic to count_loc.py
# ---------------------------------------------------------------------------

def count_lines_in_file(filepath: Path) -> int:
    """Count code lines, skipping blanks and comments (// and /* */)."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return 0

    code_lines = 0
    in_multiline = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if "/*" in stripped:
            in_multiline = True
        if "*/" in stripped:
            in_multiline = False
            after = stripped.split("*/", 1)[-1].strip()
            if after and not after.startswith("//"):
                code_lines += 1
            continue
        if in_multiline:
            continue
        if stripped.startswith("//"):
            continue
        code_lines += 1

    return code_lines


# ---------------------------------------------------------------------------
# Reference detection
# ---------------------------------------------------------------------------

def find_pkg_refs_in_files(sv_files: list, all_pkg_stems: set) -> set:
    """Find all package stems referenced (via ::) in a list of SV files."""
    refs = set()
    for f in sv_files:
        try:
            text = Path(f).read_text(errors="replace")
        except Exception:
            continue
        for m in re.finditer(r"\b(\w+)::", text):
            name = m.group(1)
            if name in all_pkg_stems:
                refs.add(name)
    return refs


def find_mod_refs_in_files(sv_files: list, mod_index: dict) -> set:
    """
    Find module stems instantiated in a list of SV files.
    Uses two complementary patterns that reliably identify SV module instantiation:
      1. `module_name #(` — parameterized instantiation
      2. `module_name u_xxx` / `module_name i_xxx` / `module_name gen_xxx` —
         OT's conventional instance-name prefixes (u_, i_, gen_, g_)

    Both patterns filter by membership in mod_index to avoid false positives.
    """
    mod_stems = set(mod_index.keys())
    refs = set()

    # Pattern 1: parameterized — `word #(`
    _param_re  = re.compile(r"\b(\w+)\s*#\s*\(")
    # Pattern 2: non-parameterized with OT instance-name prefixes
    _noparam_re = re.compile(r"\b(\w+)\s+(?:u_|i_|gen_|g_)\w")

    for f in sv_files:
        try:
            text = Path(f).read_text(errors="replace")
        except Exception:
            continue
        for m in _param_re.finditer(text):
            name = m.group(1)
            if name in mod_stems:
                refs.add(name)
        for m in _noparam_re.finditer(text):
            name = m.group(1)
            if name in mod_stems:
                refs.add(name)
    return refs


def find_pkg_deps_in_file(pkg_path: Path, all_pkg_stems: set) -> set:
    """Return set of package stems that a single pkg file depends on."""
    try:
        text = pkg_path.read_text(errors="replace")
    except Exception:
        return set()
    deps = set()
    for m in re.finditer(r"\b(\w+)::", text):
        name = m.group(1)
        if name in all_pkg_stems and name != pkg_path.stem:
            deps.add(name)
    return deps


# ---------------------------------------------------------------------------
# Build global indexes
# ---------------------------------------------------------------------------

def _priority_for(folder_name: str) -> int:
    """Lower = higher priority."""
    try:
        return INDEX_PRIORITY.index(folder_name)
    except ValueError:
        return len(INDEX_PRIORITY)


def _build_index(ot_hw_dir: Path, pkg_only: bool) -> dict:
    """
    Generic index builder.
    pkg_only=True  → only *_pkg.sv files
    pkg_only=False → only non-*_pkg.sv files

    Covers:
      - hw/ip/*/rtl/
      - hw/top_earlgrey/rtl/ and hw/top_earlgrey/rtl/autogen/
      - hw/top_earlgrey/ip/*/rtl/
    """
    index: dict = {}  # stem -> (priority, Path)

    def _add(path: Path, folder_name: str):
        stem = path.stem
        is_pkg = stem.endswith("_pkg")
        if pkg_only and not is_pkg:
            return
        if not pkg_only and is_pkg:
            return
        prio = _priority_for(folder_name)
        if stem not in index or prio < index[stem][0]:
            index[stem] = (prio, path)

    ip_dir = ot_hw_dir / "ip"
    if ip_dir.is_dir():
        for design_dir in sorted(ip_dir.iterdir()):
            if not design_dir.is_dir():
                continue
            rtl_dir = design_dir / "rtl"
            if rtl_dir.is_dir():
                for sv in rtl_dir.glob("*.sv"):
                    _add(sv, design_dir.name)

    for top_name in ("top_earlgrey", "top_darjeeling"):
        top_dir = ot_hw_dir / top_name
        if not top_dir.is_dir():
            continue
        for rtl_sub in (top_dir / "rtl", top_dir / "rtl" / "autogen"):
            if rtl_sub.is_dir():
                for sv in rtl_sub.glob("*.sv"):
                    _add(sv, top_name)
        if (top_dir / "ip").is_dir():
            for ip_sub in sorted((top_dir / "ip").glob("*/rtl")):
                for sv in ip_sub.glob("*.sv"):
                    _add(sv, top_name)

    return {stem: path for stem, (_, path) in index.items()}


def build_pkg_index(ot_hw_dir: Path) -> dict:
    """stem -> Path for all *_pkg.sv files."""
    return _build_index(ot_hw_dir, pkg_only=True)


def build_mod_index(ot_hw_dir: Path) -> dict:
    """stem -> Path for all non-*_pkg .sv files."""
    return _build_index(ot_hw_dir, pkg_only=False)


# ---------------------------------------------------------------------------
# Transitive resolution
# ---------------------------------------------------------------------------

def resolve_pkg_deps_transitive(
    own_files: list,
    own_pkg_stems: set,
    pkg_index: dict,
) -> set:
    """
    BFS from package refs in own_files.
    Returns the set of external package stems needed (excluding own pkgs).
    """
    all_pkg_stems = set(pkg_index.keys())
    seed = find_pkg_refs_in_files(own_files, all_pkg_stems) - own_pkg_stems

    visited: set = set()
    queue: deque = deque(seed)
    while queue:
        stem = queue.popleft()
        if stem in visited:
            continue
        visited.add(stem)
        pkg_path = pkg_index.get(stem)
        if pkg_path is None:
            continue
        for dep in find_pkg_deps_in_file(pkg_path, all_pkg_stems):
            if dep not in visited and dep not in own_pkg_stems:
                queue.append(dep)
    return visited


def resolve_mod_deps_transitive(
    seed_files: list,
    own_mod_stems: set,
    mod_index: dict,
    pkg_index: dict,
    known_pkg_stems: set,
) -> tuple:
    """
    BFS from module refs in seed_files.
    When a dep module is found, scan it for further module AND package refs.
    Returns (mod_stems_needed: set, extra_pkg_stems: set).

    own_mod_stems: module stems defined in design's own rtl/ — excluded from deps.
    known_pkg_stems: pkg stems already resolved — skip re-adding them.
    """
    all_pkg_stems = set(pkg_index.keys())

    visited_mods: set = set()
    extra_pkgs: set = set()
    queue: deque = deque(find_mod_refs_in_files(seed_files, mod_index) - own_mod_stems)

    while queue:
        stem = queue.popleft()
        if stem in visited_mods:
            continue
        visited_mods.add(stem)
        mod_path = mod_index.get(stem)
        if mod_path is None:
            continue

        # Scan this module for further module refs
        new_mod_refs = find_mod_refs_in_files([mod_path], mod_index) - own_mod_stems
        for dep in new_mod_refs:
            if dep not in visited_mods:
                queue.append(dep)

        # Also catch any pkg refs this module introduces
        new_pkg_refs = find_pkg_refs_in_files([mod_path], all_pkg_stems)
        for pkg in new_pkg_refs:
            if pkg not in known_pkg_stems and pkg not in extra_pkgs:
                extra_pkgs.add(pkg)
                # Transitively resolve this new pkg too
                pkg_path = pkg_index.get(pkg)
                if pkg_path:
                    for dep in find_pkg_deps_in_file(pkg_path, all_pkg_stems):
                        if dep not in known_pkg_stems:
                            extra_pkgs.add(dep)

    return visited_mods, extra_pkgs


# ---------------------------------------------------------------------------
# Design enumeration
# ---------------------------------------------------------------------------

def get_design_dirs(ip_dir: Path, exclude: set) -> list:
    """Return list of (design_name, rtl_dir) for all ip/* with *.sv files."""
    designs = []
    for d in sorted(ip_dir.iterdir()):
        if not d.is_dir() or d.name in exclude:
            continue
        rtl_dir = d / "rtl"
        if not rtl_dir.is_dir():
            continue
        if list(rtl_dir.glob("*.sv")):
            designs.append((d.name, rtl_dir))
    return designs


# ---------------------------------------------------------------------------
# Per-design LOC
# ---------------------------------------------------------------------------

def count_design_loc(
    design_name: str,
    rtl_dir: Path,
    pkg_index: dict,
    mod_index: dict,
) -> dict:
    own_sv = sorted(rtl_dir.glob("*.sv"))
    own_pkg_stems = {f.stem for f in own_sv if f.name.endswith("_pkg.sv")}
    own_mod_stems = {f.stem for f in own_sv if not f.name.endswith("_pkg.sv")}

    # --- Own LOC ---
    own_file_details = []
    own_total = 0
    for f in own_sv:
        loc = count_lines_in_file(f)
        own_total += loc
        own_file_details.append((f.name, loc))

    # --- Package deps ---
    pkg_stems = resolve_pkg_deps_transitive(own_sv, own_pkg_stems, pkg_index)
    pkg_paths = [pkg_index[s] for s in pkg_stems if s in pkg_index]

    pkg_file_details = []
    pkg_total = 0
    for path in sorted(pkg_paths, key=lambda p: p.name):
        loc = count_lines_in_file(path)
        pkg_total += loc
        pkg_file_details.append((path.name, loc))

    # --- Module deps (transitive, starting from own files + pkg files) ---
    # Also seed from prim_flop_macros.sv: its `define bodies expand to instantiate
    # prim_sparse_fsm_flop and similar modules that are invisible in the design files.
    macro_seeds = []
    for special in ("prim_flop_macros",):
        if special in mod_index:
            macro_seeds.append(mod_index[special])
    seed_files = list(own_sv) + pkg_paths + macro_seeds
    mod_stems, extra_pkg_stems = resolve_mod_deps_transitive(
        seed_files, own_mod_stems, mod_index, pkg_index, pkg_stems
    )

    # Add any extra packages discovered via module scanning
    for stem in extra_pkg_stems - pkg_stems:
        pkg_path = pkg_index.get(stem)
        if pkg_path:
            loc = count_lines_in_file(pkg_path)
            pkg_total += loc
            pkg_file_details.append((pkg_path.name, loc))
            pkg_stems.add(stem)

    mod_file_details = []
    mod_total = 0
    for stem in sorted(mod_stems):
        mod_path = mod_index.get(stem)
        if mod_path is None:
            continue
        loc = count_lines_in_file(mod_path)
        mod_total += loc
        mod_file_details.append((mod_path.name, loc))

    return {
        "own_rtl":  own_total,
        "pkg_deps": pkg_total,
        "mod_deps": mod_total,
        "total":    own_total + pkg_total + mod_total,
        "own_files": own_file_details,
        "pkg_files": pkg_file_details,
        "mod_files": mod_file_details,
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(results: dict, sort_by: str = "own_rtl", verbose: bool = False):
    sort_key = {
        "own_rtl":  lambda x: x[1]["own_rtl"],
        "mod_deps": lambda x: x[1]["mod_deps"],
        "total":    lambda x: x[1]["total"],
        "name":     lambda x: x[0],
    }.get(sort_by, lambda x: x[1]["own_rtl"])

    reverse = sort_by != "name"
    sorted_results = sorted(results.items(), key=sort_key, reverse=reverse)

    print(f"\nOT IP LOC count (opentitan/hw/ip/) — sorted by {sort_by}\n")

    s_own = s_pkg = s_mod = s_tot = 0
    W = 88  # separator width
    for design_name, data in sorted_results:
        own = data["own_rtl"]
        pkg = data["pkg_deps"]
        mod = data["mod_deps"]
        tot = data["total"]
        s_own += own; s_pkg += pkg; s_mod += mod; s_tot += tot

        # print("-" * W)
        print(
            f"{design_name:<26}  {own:>7,}  pkg_deps ={pkg:>7,}"
            f"  mod_deps ={mod:>7,}  total ={tot:>7,}"
        )

        if verbose:
            if data["own_files"]:
                print("  [own rtl]")
                for fname, loc in data["own_files"]:
                    print(f"    {fname}: {loc:,}")
            if data["pkg_files"]:
                print("  [pkg deps]")
                for fname, loc in sorted(data["pkg_files"]):
                    print(f"    {fname}: {loc:,}")
            if data["mod_files"]:
                print("  [mod deps]")
                for fname, loc in sorted(data["mod_files"]):
                    print(f"    {fname}: {loc:,}")

    print("\n" + "=" * W)
    print(
        f"{'TOTAL':<26}  own={s_own:>6,}  pkg_deps={s_pkg:>6,}"
        f"  mod_deps={s_mod:>7,}  total={s_tot:>7,}"
    )
    print(f"Designs counted: {len(results)}")
    print("=" * W + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Count LOC for all OT IP designs in opentitan/hw/ip/."
    )
    parser.add_argument(
        "--ot-dir", default=None,
        help="Path to opentitan/ root (default: <project_root>/opentitan)"
    )
    parser.add_argument(
        "--sort-by",
        choices=["own_rtl", "mod_deps", "total", "name"],
        default="own_rtl",
        help="Sort output by own_rtl (default), mod_deps, total, or name"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show per-file LOC breakdown"
    )
    parser.add_argument(
        "--design", default=None,
        help="Only measure a single design (e.g. adc_ctrl)"
    )
    parser.add_argument(
        "--exclude", default=",".join(sorted(INFRA_EXCLUDES)),
        help=f"Comma-separated ip folder names to exclude from design list "
             f"(default: {','.join(sorted(INFRA_EXCLUDES))})"
    )
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    ot_root   = Path(args.ot_dir) if args.ot_dir else project_root / "opentitan"
    ot_hw_dir = ot_root / "hw"
    ip_dir    = ot_hw_dir / "ip"

    if not ip_dir.is_dir():
        print(f"ERROR: opentitan/hw/ip/ not found at {ip_dir}", file=sys.stderr)
        sys.exit(1)

    exclude_set = {s.strip() for s in args.exclude.split(",") if s.strip()}

    print(f"Building indexes from {ot_hw_dir} ...", file=sys.stderr)
    pkg_index = build_pkg_index(ot_hw_dir)
    mod_index = build_mod_index(ot_hw_dir)
    print(f"  {len(pkg_index)} package stems, {len(mod_index)} module stems.", file=sys.stderr)

    if args.design:
        rtl_dir = ip_dir / args.design / "rtl"
        if not rtl_dir.is_dir():
            print(f"ERROR: rtl/ not found for design '{args.design}': {rtl_dir}", file=sys.stderr)
            sys.exit(1)
        designs = [(args.design, rtl_dir)]
    else:
        designs = get_design_dirs(ip_dir, exclude_set)

    print(f"Counting LOC for {len(designs)} designs ...", file=sys.stderr)

    results = {}
    for design_name, rtl_dir in designs:
        results[design_name] = count_design_loc(design_name, rtl_dir, pkg_index, mod_index)

    print_report(results, sort_by=args.sort_by, verbose=args.verbose)


if __name__ == "__main__":
    main()
