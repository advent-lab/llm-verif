#!/usr/bin/env python3
"""
plot_tok_vs_cov.py
-------------------
Render a tokens-vs-coverage% line chart for a single run.

Usage
-----
    python plot_tok_vs_cov.py <path_to_tokens.json>

Reads the `coverage_curve` field written by compute_covagent.py (one
{turn, total_tokens, coverage_pct} entry per turn), cleans it into a
monotonic curve, and writes tok_vs_cov.html next to the input file.
"""

import argparse
import json
import sys
from pathlib import Path

import plotly.graph_objects as go


def clean_curve(curve):
    """
    Build a monotonic (tokens, coverage_pct, turn) curve from a run's
    coverage_curve.

    total_tokens can *decrease* between turns (context pruning/compaction),
    so the x-axis uses the running max of total_tokens ("peak context used
    so far"). Coverage is already non-decreasing across turns.
    """
    tokens = [pt["total_tokens"] for pt in curve]
    cov_pct = [pt["coverage_pct"] for pt in curve]
    turns = [pt["turn"] for pt in curve]

    # Drop bogus zero-token entries that appear after the curve has started
    # (e.g. a corrupt final entry with total_tokens=0 but high coverage).
    # Leading (0, 0%) entries are kept.
    valid = [t > 0 for t in tokens]
    for i in range(len(tokens)):
        if tokens[i] == 0 and cov_pct[i] == 0:
            valid[i] = True
        else:
            break

    tokens = [t for t, v in zip(tokens, valid) if v]
    cov_pct = [c for c, v in zip(cov_pct, valid) if v]
    turns = [tn for tn, v in zip(turns, valid) if v]

    if not tokens:
        return [0.0], [0.0], [0]

    # Running max: makes the token axis monotonically non-decreasing.
    peak = 0.0
    for i, t in enumerate(tokens):
        peak = max(peak, t)
        tokens[i] = peak

    # Collapse plateaus from the running max (keep the last / highest-coverage
    # point at each token value).
    keep_tokens, keep_cov, keep_turns = [], [], []
    n = len(tokens)
    for i in range(n):
        if i + 1 < n and tokens[i + 1] == tokens[i]:
            continue
        keep_tokens.append(tokens[i])
        keep_cov.append(cov_pct[i])
        keep_turns.append(turns[i])

    # Ensure the curve starts at the origin.
    if keep_tokens[0] > 0:
        keep_tokens = [0.0] + keep_tokens
        keep_cov = [0.0] + keep_cov
        keep_turns = [0] + keep_turns

    return keep_tokens, keep_cov, keep_turns


def build_figure(tokens, cov_pct, turns, design_name):
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=tokens,
            y=cov_pct,
            mode="lines+markers",
            line=dict(color="#1a5a9e", width=2.5),
            marker=dict(size=6),
            hovertemplate="Turn %{customdata}<br>Tokens: %{x:,}<br>Coverage: %{y:.2f}%<extra></extra>",
            customdata=turns,
        )
    )

    fig.update_layout(
        title=dict(
            text=f"<b>Tokens vs. Coverage: {design_name}</b>",
            x=0.5,
            xanchor="center",
            font=dict(size=16),
        ),
        xaxis=dict(title="Cumulative Tokens", tickformat=","),
        yaxis=dict(title="Coverage (%)", range=[0, 105]),
        template="plotly_white",
        width=900,
        height=600,
    )
    return fig


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a tokens-vs-coverage line chart for a single run's tokens.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python scripts/plot_tok_vs_cov.py work/chacha_top/tokens.json
        """,
    )
    parser.add_argument("json_path", type=str, help="Path to tokens.json")
    args = parser.parse_args()

    json_path = Path(args.json_path)
    if not json_path.exists() or not json_path.is_file():
        print(f"Error: File does not exist: {json_path}", file=sys.stderr)
        return 1

    with open(json_path) as f:
        tokens_data = json.load(f)

    curve = tokens_data.get("coverage_curve")
    if not curve:
        print(f"Error: no 'coverage_curve' entries found in {json_path}", file=sys.stderr)
        return 1

    tokens, cov_pct, turns = clean_curve(curve)
    design_name = tokens_data.get("design", "Design")

    fig = build_figure(tokens, cov_pct, turns, design_name)

    output_path = json_path.parent / "tok_vs_cov.html"
    fig.write_html(str(output_path))
    print(f"Chart saved to: {output_path}")
    print(f"Final coverage: {cov_pct[-1]:.2f}% at {tokens[-1]:,.0f} tokens")

    return 0


if __name__ == "__main__":
    sys.exit(main())
