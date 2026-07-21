# CovAgent

An LLM-based agent for automated stimulus generation and coverage closure in hardware verification. The agent reads design specifications, generates SystemVerilog testbenches, runs simulations, and iteratively improves coverage. When coverage targets are reached or no further progress can be made, the agent writes a final run report. 

The framework is designed for in-depth visibility and traceability with comprehensive agent logging, allowing studies on token allocation and coverage limits in agentic stimulus generation.

> **Spec2Cov** is the predecessor project available on the [`Spec2Cov` branch](https://github.com/advent-lab/llm-verif/tree/Spec2Cov).

## Research Overview

CovAgent is the foundation of the MLCAD paper "Understanding Inference-Time Token Allocation and Coverage Limits in Agentic Hardware Verification," which studies two open questions about LLM-based coverage closure: which residual coverage holes LLM-generated stimulus cannot close, and where inference-time tokens are consumed/generated during agentic verification.

### Coverage hole taxonomy

Each run's `report.md` classifies remaining uncovered lines as either unreachable from the top-level interface or excludable (dead or defensive code). The paper aggregates these per-run classifications into a six-category taxonomy across two classes:

- **Methodology-bound ceilings** (M1-M3): tied-off integration hardware, infeasible counter/state boundaries, and defensive or dead code. Closing these requires changing the RTL integration or verification methodology, not the stimulus.
- **Reasoning frontiers** (R1-R3): protocol sequencing complexity, multi-module pipeline warm-up, and narrow timing or rare-input conditions. These are coverable in principle and form the improvement surface for LLM-based verification.

### Token allocation

Each run's `events.jsonl` records per-turn detail sufficient to classify every token into six categories: System Prompt, Design Comprehension, Stimulus Generation, Coverage Feedback, Error Recovery, and Agentic Overhead. Key findings:

- Only 12-18% of accumulated tokens produce testbench code; the rest covers comprehension, iteration, and agentic overhead.
- Design-comprehension reasoning scales superlinearly with design size (roughly 0.1-0.3 reasoning tokens/LOC for small designs versus 4-8 for large ones), making comprehension the bottleneck at scale.
- Roughly 40% of total tokens are spent after coverage has plateaued.

The [Generating Token Allocation Breakdown](#generating-token-allocation-breakdown) section covers scripts utilizing logs to generate the token-allocation and tokens-vs-coverage plots for a single run.

## Quick Start

### Prerequisites

- QuestaSim or Verilator installed
- Python 3.8+
- OpenAI API key (or other LLM provider)

### Installation

**No package installation required** - the framework uses direct imports via path manipulation.

```bash
# 1. Create Python environment (skip if exists)
mamba create -n lg_venv -c conda-forge pip -y # SOL-specific

# 2. Activate environment
module load mamba/latest
module load bittware/questa-23.4
source activate lg_venv

# 3. Install Python dependencies
pip install -r requirements.txt
```

### Configure Environment

Create or copy an environment file:

```bash
cp .env.example .env
```

See existing configs in `configs/` for examples. Full variable reference below.

### Running the Agent

```bash
# Use default .env file in project root
python run_agent.py

# Specify custom config file
python run_agent.py -e configs/codex-vs-react.env
python run_agent.py --env-file path/to/custom.env

# Validate config without running
python run_agent.py --validate-only

# Get help
python run_agent.py --help
```

## Configuration

Create a `.env` file or use configs from `configs/`. See [docs/CONFIG.md](docs/CONFIG.md) for the full reference.

### Required

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `COMPILER` | Path to simulator binaries directory |
| `SIMULATOR` | `questasim` or `verilator` |
| `DESIGN_NAME` | Design name (must exist in dashboard) |
| `DASHBOARD_PATH` | Path to dashboard.json |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL` | `gpt-4o` | LLM model |
| `TEMPERATURE` | `0.4` | Sampling temperature |
| `MAX_TOKENS` | `4096` | Max output tokens per LLM response |
| `REASONING_EFFORT` | `disabled` | O1/O3 extended thinking (`disabled`, `low`, `medium`, `high`) |
| `DESIGN_CONTEXT` | `1` | Allow agent to read RTL files (`0` = spec only) |
| `WORK_DIR` | `./work` | Output directory |
| `RUN_ID` | `default_run` | Run identifier |
| `MAX_ITERATIONS` | `10` | Max LLM API calls before stopping |
| `MAX_RETRIES` | `3` | Max consecutive compile/sim failures before stopping |
| `MAX_NO_PROGRESS` | `5` | Stop after N iterations without coverage improvement |
| `MAX_NO_TOOL_CALLS` | `3` | Stop after N consecutive responses with no tool calls |
| `KEEP_LATEST_FAILURES` | `1` | Failed verification cycles to keep in context for debugging |
| `TESTPLAN` | `1` | Generate a test plan before writing testbenches (`0` to skip) |
| `SIM_RUNS` | `5` | Simulation runs per testbench (different seeds) |
| `SIM_TIMEOUT` | `60` | Per-simulation timeout in seconds |
| `NUM_FEEDBACK_HOLES` | `0` | Priority coverage holes in feedback (0 = unbounded/all) |
| `COVERAGE_HOLE_RADIUS` | `5` | Context lines around each coverage hole (0-20) |
| `CONTEXT_WINDOW` | `128000` | Max tokens before terminating run |
| `RECURSION_LIMIT` | `300` | LangGraph recursion limit |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `LOG_TRUNCATE` | `1` | Truncate long tool outputs in logs (`0` = show full content) |
| `TEST_MODE` | `0` | Use mock simulator without a real installation (`1` to enable) |

## Output

All artifacts are saved to `{WORK_DIR}/{RUN_ID}/`:

```
work/my_run/
├── run.log                  # Full agent log
├── events.jsonl             # Structured event stream (one JSON object per line)
├── final_state.json         # Serialized run state
├── report.md                # Agent-written run report
├── testplan.md              # Generated test plan (optional)
├── testbenches/
│   ├── tb_iter_1.sv
│   ├── tb_iter_2.sv
│   └── ...
├── logs/
│   ├── compile_iter_1.log
│   ├── sim_iter_1.log
│   └── ...
└── coverage/
    ├── iter_1.ucdb          # Per-iteration merged coverage
    ├── cumulative.ucdb      # Cumulative coverage across all iterations
    ├── iter_1_run_0.ucdb    # Individual runs
    └── ...
```

## Generating Token Allocation Breakdown

Every run writes a complete, machine-parseable record of each LLM turn (token
usage, tool calls, coverage) to `events.jsonl` in that run's work directory
(`<WORK_DIR>/<RUN_ID>/events.jsonl`, e.g. `work/fifo_run_1/events.jsonl` with
the example `.env`). Scripts under `scripts/` turn that into the
token-allocation and tokens-vs-coverage figures used in the paper:

```bash
# 1. Categorize tokens by turn -> writes tokens.json into the run's work dir
python scripts/compute_covagent.py work/<RUN_ID>

# 2. Render the category breakdown as a pie chart -> token_alloc.html
python scripts/visualize_tokens.py work/<RUN_ID>/tokens.json

# 3. (optional) Export the category breakdown as a CSV -> by_category.csv
python scripts/make_category_csv.py work/<RUN_ID>

# 4. (optional) Plot tokens-vs-coverage for this run -> tok_vs_cov.html
python scripts/plot_tok_vs_cov.py work/<RUN_ID>/tokens.json
```

`compute_covagent.py` classifies each turn's input/output tokens into one of
six categories (System Prompt, Design Comprehension, Stimulus Generation,
Coverage Feedback, Error Recovery, Agentic Overhead) based on which tools
were called and what they touched, then aggregates totals per category into
`tokens.json`. Run `python scripts/compute_covagent.py --help` for options,
and see [scripts/README.md](scripts/README.md) for the rest of the scripts
in this directory.

## Supported Simulators

- **QuestaSim** -- Full support with UCDB statement coverage
- **Verilator** -- Line coverage (LCOV format); fully tested

## Documentation

- [docs/ARCH.md](docs/ARCH.md) -- Architecture details
- [docs/CONFIG.md](docs/CONFIG.md) -- Configuration reference
- [docs/DEV.md](docs/DEV.md) -- Developer setup and guide
- [scripts/README.md](scripts/README.md) -- Script-by-script usage reference

## Project Structure

```
llm-verif/
├── run_agent.py          # CLI entry point
├── configs/              # Example environment configs
├── src/
│   ├── config.py         # Configuration loading
│   ├── main.py           # Simpler entry point
│   ├── graphs/react.py   # LangGraph agent (nodes, edges, routing)
│   ├── state/            # State schema (AgentState)
│   ├── tools/            # Agent tools (compile, simulate, coverage, filesystem)
│   ├── simulators/       # Simulator adapters (QuestaSim, Verilator)
│   ├── utils/            # Token counting, design loading, dashboard loader
│   └── prompts/          # System prompt template
├── scripts/              # Result analysis and standalone sanity-check scripts
└── data/                 # Design files (RTL + specs)
```
