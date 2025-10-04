from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple
import os, csv, fnmatch

# pip install lcovparser
from lcovparser import parse_file as lcov_parse_file, Report, Record

def _norm(p: str) -> str:
    return os.path.normpath(p).replace("\\", "/")

def _should_exclude(path: str, patterns: Iterable[str]) -> bool:
    """
    Return True if 'path' matches any pattern in 'patterns'.
    Patterns are tested against both the normalized full path and the basename.
    Supports shell-style globs: *, **, ?. Examples:
      "*/tb_*", "*_tb.sv", "tb_sha1.sv", "tests/**", "**/sim/*"
    """
    if not patterns:
        return False
    npath = _norm(path)
    base = os.path.basename(npath)
    for pat in patterns:
        if fnmatch.fnmatch(npath, pat) or fnmatch.fnmatch(base, pat):
            return True
    return False

@dataclass
class FileCoverage:
    file: str
    lines_found: int
    lines_hit: int
    coverage_pct: float
    uncovered_lines: List[int]

def load_file_coverage(
    info_path: str,
    exclude: Iterable[str] = (),
    ignore_incorrect_counts: bool = True,
    merge_duplicate_line_hit_counts: bool = True,
) -> List[FileCoverage]:
    """
    Parse LCOV .info and return by-file coverage (excluding any file that matches 'exclude').
    """
    report: Report = lcov_parse_file(
        info_path,
        ignore_incorrect_counts=ignore_incorrect_counts,
        merge_duplicate_line_hit_counts=merge_duplicate_line_hit_counts,
    )

    rows: List[FileCoverage] = []
    for filename in report:
        rec: Record = report[filename]
        if _should_exclude(rec.filename, exclude):
            continue

        lines_found = len(rec.lines)
        lines_hit = sum(1 for hits in rec.lines.values() if hits > 0)
        pct = (lines_hit / lines_found * 100.0) if lines_found else 0.0
        uncovered = sorted(ln for ln, hits in rec.lines.items() if hits == 0)

        rows.append(FileCoverage(
            file=_norm(rec.filename),
            lines_found=lines_found,
            lines_hit=lines_hit,
            coverage_pct=round(pct, 2),
            uncovered_lines=uncovered,
        ))

    # Sort: lowest coverage first, then larger files first, then filename
    rows.sort(key=lambda r: (r.coverage_pct, -r.lines_found, r.file))
    return rows

def worst_files(rows: List[FileCoverage], top_k: int = 10, min_lines: int = 1) -> List[FileCoverage]:
    """Pick the K worst-covered files, ignoring tiny files if desired."""
    cand = [r for r in rows if r.lines_found >= min_lines]
    cand.sort(key=lambda r: (r.coverage_pct, -r.lines_found, r.file))
    return cand[:top_k]

def total_coverage(rows: List[FileCoverage]) -> Tuple[int, int, float]:
    """
    Aggregate total coverage across all provided files.
    Returns (total_lines_found, total_lines_hit, coverage_pct).
    """
    lf = sum(r.lines_found for r in rows)
    lh = sum(r.lines_hit for r in rows)
    pct = (lh / lf * 100.0) if lf else 0.0
    return lf, lh, round(pct, 2)

def write_file_coverage_csv(rows: List[FileCoverage], out_csv: str) -> None:
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "lines_found", "lines_hit", "coverage_pct", "uncovered_lines"])
        for r in rows:
            w.writerow([r.file, r.lines_found, r.lines_hit, f"{r.coverage_pct:.2f}",
                        " ".join(map(str, r.uncovered_lines))])

