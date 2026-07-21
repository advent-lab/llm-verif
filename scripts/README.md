# scripts/

Utility scripts for analyzing runs and doing standalone sanity checks outside the main agent loop.

## Token allocation pipeline

Scripts that turn a run's `events.jsonl` into the token-allocation and tokens-vs-coverage figures used in the paper. Run `compute_covagent.py` first; the rest consume its output (`tokens.json`) directly. See the "Reproducing Token Allocation Results" section in the top-level [README.md](../README.md) for a full walkthrough.

### `compute_covagent.py`

Parses `events.jsonl` (the structured event log written by every run) and classifies every input/output token into one of six categories — System Prompt, Design Comprehension, Stimulus Generation, Coverage Feedback, Error Recovery, Agentic Overhead — based on which tool was called on the preceding turn and what it touched. Writes `tokens.json` (per-category totals, per-turn breakdown, coverage curve) into the run's work directory.

```bash
python scripts/compute_covagent.py work/<RUN_ID>
```

### `visualize_tokens.py`

Reads a `tokens.json` and renders it as an interactive pie chart, split by category and by input/output/reasoning tokens within each category. Writes `token_alloc.html` next to the input file. Requires `plotly`.

```bash
python scripts/visualize_tokens.py work/<RUN_ID>/tokens.json
```

### `make_category_csv.py`

Reads a `tokens.json` and writes `by_category.csv` next to it — one row per category plus a totals row, for spreadsheet use or further plotting.

```bash
python scripts/make_category_csv.py work/<RUN_ID>
```

### `plot_tok_vs_cov.py`

Reads a `tokens.json`'s `coverage_curve` (one `{turn, total_tokens, coverage_pct}` entry per turn) and renders a tokens-vs-coverage line chart for that single run. Since the context window can shrink between turns (pruning/compaction), the token axis is built from the running max of `total_tokens` so the line is always monotonic. Writes `tok_vs_cov.html` next to the input file. Requires `plotly`.

```bash
python scripts/plot_tok_vs_cov.py work/<RUN_ID>/tokens.json
```

This is a single-run simplification — the original scripts this was adapted from (`plot_tok_vs_cov.py` / `plot_tok_vs_cov_matplotlib.py` in the paper's analysis tooling) average curves across many repeated runs and overlay every design in a batch directory on one chart, for the paper's cross-design comparison figure. That aggregation layer isn't in this repo yet.

## Standalone sanity checks

These exercise a piece of the framework in isolation, without running the full agent graph. Useful when debugging a specific component.

### `test_design.py`

Scaffolds a compile-and-simulate cycle for any design in `dashboard.json`, independent of the agent. Reads `COMPILER`, `DASHBOARD_PATH`, and `BASE_DIR` from `.env` if present. Use this to confirm a design compiles and simulates before pointing the agent at it.

```bash
python scripts/test_design.py <design_name>
python scripts/test_design.py chacha_top --compiler /path/to/questasim/bin
```

### `test_prompt_loader.py`

Exercises the system-prompt pipeline end to end: load a design (from `dashboard.json` or auto-discovered from a directory), extract RTL module headers, and render the final system prompt with all template variables filled in. Useful for checking prompt output for a design without spending API calls.

```bash
python scripts/test_prompt_loader.py --design <design_name>
```

### `gen_codex_prompt.py`

Generates the Codex-CLI system prompt for a design (used for the Codex-vs-CovAgent comparison runs referenced in the paper). Prints to stdout by default.

```bash
python scripts/gen_codex_prompt.py --design <design_name>
python scripts/gen_codex_prompt.py --design <design_name> --output prompt.txt
```
