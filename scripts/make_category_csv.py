"""
make_category_csv.py
--------------------
Read the top-level tokens.json in a results directory and write a
by_category.csv next to it.

Usage
-----
    python make_category_csv.py <parent_dir>

    e.g.   python make_category_csv.py /path/to/work/FINAL_MINI

Output
------
    <parent_dir>/by_category.csv

Columns: Category, Input Tokens, Visible Output Tokens, Reasoning Tokens,
         Total Tokens, Input Turns, Output Turns, Row Total
Rows   : one per category + a Total row.
"""

import csv
import json
import sys
from pathlib import Path

COLUMNS = [
    ("input_tokens",          "Input Tokens",          False),
    ("visible_output_tokens", "Visible Output Tokens",  False),
    ("reasoning_tokens",      "Reasoning Tokens",       False),
    ("total_tokens",          "Total Tokens",           False),
    ("num_turns_input",       "Input Turns",            True),
    ("num_turns_output",      "Output Turns",           True),
]


def main():
    if len(sys.argv) < 2:
        print("Usage: python make_category_csv.py <parent_dir>")
        sys.exit(1)

    parent = Path(sys.argv[1]).resolve()
    tok_file = parent / "tokens.json"
    if not tok_file.exists():
        print(f"Error: {tok_file} not found")
        sys.exit(1)

    with tok_file.open() as f:
        data = json.load(f)

    by_category: dict = data.get("by_category", {})
    if not by_category:
        print("Error: no 'by_category' key found in tokens.json")
        sys.exit(1)

    header = ["Category"] + [label for _, label, _ in COLUMNS] + ["Row Total"]
    rows = []
    col_totals = [0.0] * len(COLUMNS)

    for cat_name, cat in by_category.items():
        values = [cat.get(key, 0.0) for key, _, _ in COLUMNS]
        row_total = sum(values)
        rows.append([cat_name] + values + [row_total])
        for i, v in enumerate(values):
            col_totals[i] += v

    total_row = ["Total"] + col_totals + [sum(col_totals)]
    rows.append(total_row)

    # decimals flag per column (True = keep decimals, False = round to int)
    decimals_flags = [keep for _, _, keep in COLUMNS]

    def fmt(v, keep_decimals):
        if not isinstance(v, float):
            return v
        return f"{v:.2f}" if keep_decimals else str(round(v))

    out_path = parent / "by_category.csv"
    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in rows:
            cat = row[0]
            vals = row[1:-1]   # per-column values
            row_total = row[-1]
            formatted = [cat]
            for v, keep in zip(vals, decimals_flags):
                formatted.append(fmt(v, keep))
            formatted.append(str(round(row_total)) if isinstance(row_total, float) else row_total)
            writer.writerow(formatted)

    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
