#!/usr/bin/env python3
"""Parse coverage reports from work/ directory and generate an Excel summary.

Each iteration column shows what that iteration's testbench achieved on its own.
The "Final (merged)" column shows QuestaSim's vcover merge of all iterations,
which is always >= any individual iteration.

Note: covergroup definitions may change between iterations (the LLM rewrites
the testbench), so per-iteration numbers are not directly cumulative.
The merged result handles this correctly.
"""

import glob
import os
import re
import xml.etree.ElementTree as ET
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

WORK_DIR = os.path.join(os.path.dirname(__file__), "work")

DESIGNS = {
    "alu": "cvdp+agentic_alu_uvm",
    "memory_scheduler": "cvdp+agentic_memory_scheduler_uvm",
    "rgb_color_space": "cvdp+agentic_rgb_color_space_conversion_uvm",
}


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_text_summary(filepath):
    """Extract TOTAL COVERGROUP COVERAGE from a text coverage report."""
    covergroup_cov = None
    with open(filepath, "r") as f:
        for line in f:
            m = re.search(r"TOTAL COVERGROUP COVERAGE:\s+([\d.]+)%", line)
            if m:
                covergroup_cov = float(m.group(1))
    return covergroup_cov


def parse_text_covergroup_types(filepath):
    """Extract per-covergroup TYPE percentages from a text report.

    Returns dict of {cg_name: pct}.  Only the first occurrence of each
    TYPE line is used (the report repeats them in the summary section).
    """
    cg_pcts = {}
    with open(filepath, "r") as f:
        for line in f:
            # TYPE line may wrap:  " TYPE /path/cg_name  \n   100.00%..."
            # or be on one line:   " TYPE /path/cg_name   100.00%  100  -  Covered"
            m = re.match(r"^\s*TYPE\s+\S+/(\w+)\s+([\d.]+)%", line)
            if m:
                name = m.group(1)
                if name not in cg_pcts:
                    cg_pcts[name] = float(m.group(2))
    return cg_pcts


def parse_text_covergroup_types_multiline(filepath):
    """Handle TYPE lines where the percentage is on the next line."""
    cg_pcts = {}
    with open(filepath, "r") as f:
        lines = f.readlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        # Single-line TYPE with percentage
        m = re.match(r"^\s*TYPE\s+\S+/(\w+)\s+([\d.]+)%", line)
        if m:
            name = m.group(1)
            if name not in cg_pcts:
                cg_pcts[name] = float(m.group(2))
            i += 1
            continue
        # Multi-line TYPE: name on this line, percentage on next
        m = re.match(r"^\s*TYPE\s+\S+/(\w+)\s*$", line)
        if m and i + 1 < len(lines):
            name = m.group(1)
            m2 = re.match(r"^\s+([\d.]+)%", lines[i + 1])
            if m2 and name not in cg_pcts:
                cg_pcts[name] = float(m2.group(1))
            i += 2
            continue
        i += 1
    return cg_pcts


def parse_xml_stmt_coverage(filepath):
    """Extract overall statement coverage % from XML report."""
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        total_active = 0
        total_hits = 0
        for du in root.iter("DuData"):
            stmts = du.find("statements")
            if stmts is not None:
                total_active += int(stmts.get("active", 0))
                total_hits += int(stmts.get("hits", 0))
        if total_active > 0:
            return total_hits / total_active * 100
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

def collect_data():
    """Collect coverage data from all runs."""
    data = {}
    for design_label, design_prefix in DESIGNS.items():
        data[design_label] = {}
        for run_num in range(1, 5):
            run_dir = os.path.join(WORK_DIR, f"{design_prefix}_run_{run_num}")
            if not os.path.isdir(run_dir):
                continue
            cov_dir = os.path.join(run_dir, "coverage")

            # Discover iteration text reports
            iter_txts = sorted(glob.glob(os.path.join(cov_dir, "functional_coverage_iter_*.txt")))
            iter_nums = []
            for txt_path in iter_txts:
                m = re.search(r"functional_coverage_iter_(\d+)\.txt", txt_path)
                if m:
                    iter_nums.append(int(m.group(1)))
            iter_nums.sort()

            # Build iter_num -> xml map
            iter_xml_map = {}
            for xp in glob.glob(os.path.join(cov_dir, "iter_*_report.xml")):
                m = re.search(r"iter_(\d+)_report\.xml", xp)
                if m:
                    iter_xml_map[int(m.group(1))] = xp

            # Per-iteration data
            iterations = {}
            for iter_num in iter_nums:
                txt_path = os.path.join(cov_dir, f"functional_coverage_iter_{iter_num}.txt")
                funcov = parse_text_summary(txt_path)
                cg_pcts = parse_text_covergroup_types_multiline(txt_path)

                stmt = None
                if iter_num in iter_xml_map:
                    stmt = parse_xml_stmt_coverage(iter_xml_map[iter_num])

                iterations[iter_num] = {
                    "funcov_pct": funcov,
                    "stmt_pct": stmt,
                    "cg_pcts": cg_pcts,
                }

            # Cumulative (final merged)
            cum_txt = os.path.join(cov_dir, "cumulative_functional_coverage.txt")
            cum_funcov = None
            cum_cg_pcts = {}
            if os.path.exists(cum_txt):
                cum_funcov = parse_text_summary(cum_txt)
                cum_cg_pcts = parse_text_covergroup_types_multiline(cum_txt)

            cum_xml = os.path.join(cov_dir, "cumulative_report.xml")
            cum_stmt = None
            if os.path.exists(cum_xml):
                cum_stmt = parse_xml_stmt_coverage(cum_xml)

            data[design_label][run_num] = {
                "iterations": iterations,
                "iter_nums": iter_nums,
                "cumulative": {
                    "funcov_pct": cum_funcov,
                    "stmt_pct": cum_stmt,
                    "cg_pcts": cum_cg_pcts,
                },
            }
    return data


# ---------------------------------------------------------------------------
# Excel generation
# ---------------------------------------------------------------------------

def create_excel(data, output_path):
    wb = Workbook()

    # Styles
    header_font = Font(bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    subheader_fill = PatternFill(start_color="D6E4F0", end_color="D6E4F0", fill_type="solid")
    subheader_font = Font(bold=True, size=10)
    cum_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    pct_format = "0.00%"
    center = Alignment(horizontal="center", vertical="center")
    wrap_center = Alignment(horizontal="center", vertical="center", wrap_text=True)

    def style_header(ws, row, c1, c2):
        for col in range(c1, c2 + 1):
            cell = ws.cell(row=row, column=col)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = wrap_center
            cell.border = thin_border

    def style_subheader(ws, row, c1, c2):
        for col in range(c1, c2 + 1):
            cell = ws.cell(row=row, column=col)
            cell.font = subheader_font
            cell.fill = subheader_fill
            cell.alignment = center
            cell.border = thin_border

    def write_pct(ws, row, col, val, bold=False, fill=None):
        cell = ws.cell(row=row, column=col)
        if val is not None:
            cell.value = val / 100.0
            cell.number_format = pct_format
        else:
            cell.value = "N/A"
        cell.alignment = center
        cell.border = thin_border
        if bold:
            cell.font = Font(bold=True)
        if fill:
            cell.fill = fill

    def write_text(ws, row, col, val, bold=False, fill=None):
        cell = ws.cell(row=row, column=col)
        cell.value = val
        cell.alignment = center
        cell.border = thin_border
        if bold:
            cell.font = Font(bold=True)
        if fill:
            cell.fill = fill

    # Max iterations across all runs
    max_iters = 0
    for dl in data:
        for rn in data[dl]:
            n = len(data[dl][rn]["iter_nums"])
            max_iters = max(max_iters, n)

    # ===== Sheet 1: Functional Coverage (Covergroup %) =====
    ws = wb.active
    ws.title = "Functional Coverage"

    # Build header: Design | Run | Iter 1 | Iter 2 | ... | Final (merged)
    headers = ["Design", "Run"]
    for i in range(1, max_iters + 1):
        headers.append(f"Iter {i}")
    headers.append("Final\n(merged)")
    max_col = len(headers)

    for ci, h in enumerate(headers, 1):
        ws.cell(row=1, column=ci, value=h)
    style_header(ws, 1, 1, max_col)
    ws.row_dimensions[1].height = 30

    row = 2
    for design_label in DESIGNS:
        if design_label not in data:
            continue
        for run_num in sorted(data[design_label]):
            rd = data[design_label][run_num]
            iters = rd["iterations"]
            iter_nums = rd["iter_nums"]
            cum = rd["cumulative"]

            write_text(ws, row, 1, design_label)
            write_text(ws, row, 2, f"run_{run_num}")

            for idx, iter_num in enumerate(iter_nums):
                write_pct(ws, row, 3 + idx, iters[iter_num]["funcov_pct"])

            # Fill unused slots
            for i in range(len(iter_nums), max_iters):
                write_text(ws, row, 3 + i, "-")

            # Final merged
            write_pct(ws, row, 3 + max_iters, cum["funcov_pct"], bold=True, fill=cum_fill)
            row += 1

    ws.column_dimensions[get_column_letter(1)].width = 20
    ws.column_dimensions[get_column_letter(2)].width = 10
    for c in range(3, max_col + 1):
        ws.column_dimensions[get_column_letter(c)].width = 14

    # ===== Sheet 2: Code Coverage (Statement %) =====
    ws = wb.create_sheet(title="Code Coverage")

    headers2 = ["Design", "Run"]
    for i in range(1, max_iters + 1):
        headers2.append(f"Iter {i}")
    headers2.append("Final\n(merged)")
    max_col2 = len(headers2)

    for ci, h in enumerate(headers2, 1):
        ws.cell(row=1, column=ci, value=h)
    style_header(ws, 1, 1, max_col2)
    ws.row_dimensions[1].height = 30

    row = 2
    for design_label in DESIGNS:
        if design_label not in data:
            continue
        for run_num in sorted(data[design_label]):
            rd = data[design_label][run_num]
            iters = rd["iterations"]
            iter_nums = rd["iter_nums"]
            cum = rd["cumulative"]

            write_text(ws, row, 1, design_label)
            write_text(ws, row, 2, f"run_{run_num}")

            for idx, iter_num in enumerate(iter_nums):
                write_pct(ws, row, 3 + idx, iters[iter_num].get("stmt_pct"))

            for i in range(len(iter_nums), max_iters):
                write_text(ws, row, 3 + i, "-")

            write_pct(ws, row, 3 + max_iters, cum.get("stmt_pct"), bold=True, fill=cum_fill)
            row += 1

    ws.column_dimensions[get_column_letter(1)].width = 20
    ws.column_dimensions[get_column_letter(2)].width = 10
    for c in range(3, max_col2 + 1):
        ws.column_dimensions[get_column_letter(c)].width = 14

    # ===== Sheet 3+: Per-design detail with covergroup breakdown =====
    for design_label in DESIGNS:
        if design_label not in data:
            continue
        ws = wb.create_sheet(title=design_label[:31])

        row = 1
        for run_num in sorted(data[design_label]):
            rd = data[design_label][run_num]
            iters = rd["iterations"]
            iter_nums = rd["iter_nums"]
            cum = rd["cumulative"]
            n_iters = len(iter_nums)
            num_cols = 2 + n_iters  # Metric col + iter cols + Final col

            # Run header
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=num_cols)
            ws.cell(row=row, column=1, value=f"Run {run_num}")
            style_header(ws, row, 1, num_cols)
            row += 1

            # Sub-headers
            write_text(ws, row, 1, "Metric")
            for idx in range(n_iters):
                write_text(ws, row, 2 + idx, f"Iter {idx + 1}")
            write_text(ws, row, 2 + n_iters, "Final (merged)")
            style_subheader(ws, row, 1, num_cols)
            row += 1

            # Covergroup % (total)
            write_text(ws, row, 1, "Covergroup %", bold=True)
            for idx, iter_num in enumerate(iter_nums):
                write_pct(ws, row, 2 + idx, iters[iter_num]["funcov_pct"])
            write_pct(ws, row, 2 + n_iters, cum["funcov_pct"], bold=True, fill=cum_fill)
            row += 1

            # Statement %
            write_text(ws, row, 1, "Statement %", bold=True)
            for idx, iter_num in enumerate(iter_nums):
                write_pct(ws, row, 2 + idx, iters[iter_num].get("stmt_pct"))
            write_pct(ws, row, 2 + n_iters, cum.get("stmt_pct"), bold=True, fill=cum_fill)
            row += 1

            # Per-covergroup rows (from final/cumulative since it has all covergroups)
            all_cg = sorted(cum.get("cg_pcts", {}).keys())
            for cg_name in all_cg:
                write_text(ws, row, 1, f"  {cg_name}")
                for idx, iter_num in enumerate(iter_nums):
                    pct = iters[iter_num].get("cg_pcts", {}).get(cg_name)
                    write_pct(ws, row, 2 + idx, pct)
                cum_pct = cum.get("cg_pcts", {}).get(cg_name)
                write_pct(ws, row, 2 + n_iters, cum_pct, bold=True, fill=cum_fill)
                row += 1

            row += 1  # blank row between runs

        ws.column_dimensions[get_column_letter(1)].width = 28
        for col in range(2, 15):
            ws.column_dimensions[get_column_letter(col)].width = 16

    output_path = os.path.abspath(output_path)
    wb.save(output_path)
    print(f"Excel saved to: {output_path}")


if __name__ == "__main__":
    data = collect_data()
    for design in data:
        for run in sorted(data[design]):
            rd = data[design][run]
            iters = rd["iterations"]
            iter_nums = rd["iter_nums"]
            cum = rd["cumulative"]
            parts = []
            for n in iter_nums:
                v = iters[n]["funcov_pct"]
                parts.append(f"{v:.1f}%" if v is not None else "N/A")
            progression = " → ".join(parts)
            final = cum["funcov_pct"]
            print(
                f"{design} run_{run}: "
                f"[{progression}] → Final {final}%"
            )
    create_excel(data, "coverage_report.xlsx")
