# CovAgent

LLM-powered automated hardware verification using LangGraph. The agent reads design specifications, generates SystemVerilog testbenches, runs simulations, and iteratively improves coverage. When coverage targets are reached or no further progress can be made, the agent writes a final run report.

## Quick Start

See [QUICK_START.md](QUICK_START.md) for installation and setup.

```bash
# Run with default .env
python run_agent.py

# Run with specific config
python run_agent.py -e configs/codex-vs-react.env

# Validate config only
python run_agent.py --validate-only
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
| `WORK_DIR` | `./work` | Output directory |
| `RUN_ID` | `default_run` | Run identifier |
| `MAX_ITERATIONS` | `10` | Max API calls / coverage iterations |
| `MAX_NO_PROGRESS` | `5` | Stop after N iterations without coverage improvement |
| `SIM_RUNS` | `5` | Simulation runs per testbench (different seeds) |
| `SIM_TIMEOUT` | `60` | Per-simulation timeout in seconds |
| `NUM_FEEDBACK_HOLES` | `0` | Priority coverage holes in feedback (0 = unbounded/all) |
| `COVERAGE_HOLE_RADIUS` | `5` | Context lines around each coverage hole (1-20) |
| `CONTEXT_WINDOW` | `128000` | Max tokens before terminating run |
| `RECURSION_LIMIT` | `300` | LangGraph recursion limit |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Output

All artifacts are saved to `{WORK_DIR}/{RUN_ID}/`:

```
work/my_run/
├── run.log                  # Full agent log
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

### Analyzing Results

```bash
# Parse run log for metrics (duration, coverage milestones, token usage)
python scripts/parse_log.py work/my_run/run.log

# JSON output for scripting
python scripts/parse_log.py work/my_run/run.log --json
```

## Supported Simulators

- **QuestaSim** -- Full support with UCDB statement coverage
- **Verilator** -- Line coverage support

## Documentation

- [QUICK_START.md](QUICK_START.md) -- Installation and setup
- [docs/ARCH.md](docs/ARCH.md) -- Architecture details
- [docs/CONFIG.md](docs/CONFIG.md) -- Configuration reference
- [docs/DEV.md](docs/DEV.md) -- Developer setup and guide

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
├── scripts/              # Log parsing, testing, and utility scripts
└── data/                 # Design files (RTL + specs)
```
