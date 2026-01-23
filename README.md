# Spec2Cov

LLM-powered automated hardware verification using LangGraph. The agent reads design specifications, generates SystemVerilog testbenches, runs simulations, and iteratively improves coverage.

## Quick Start

See [QUICK_START.md](QUICK_START.md) for installation and setup.

```bash
# Run with default .env
python run_agent.py

# Run with specific config
python run_agent.py -e configs/questasim_fifo.env

# Validate config only
python run_agent.py --validate-only
```

## Configuration

Create a `.env` file or use configs from `configs/`:

### Required

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `COMPILER` | Path to simulator binaries |
| `SIMULATOR` | `questasim` or `verilator` |
| `DESIGN_NAME` | Design name (must exist in dashboard) |
| `DASHBOARD_PATH` | Path to dashboard.json |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL` | `gpt-4o` | LLM model |
| `WORK_DIR` | `./work` | Output directory |
| `RUN_ID` | `default_run` | Run identifier |
| `MAX_ITERATIONS` | `10` | Max agent iterations |
| `MAX_NO_PROGRESS` | `5` | Stop after N iterations without coverage improvement |
| `SIM_RUNS` | `5` | Simulation runs per testbench (different seeds) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Output

All artifacts are saved to `{WORK_DIR}/{RUN_ID}/`:

```
work/my_run/
├── testbenches/
│   ├── tb_iter_1.sv
│   ├── tb_iter_2.sv
│   └── ...
├── logs/
│   ├── compile_iter_1.log
│   ├── sim_iter_1.log
│   └── ...
├── coverage/
│   ├── iter_1.ucdb          # Merged coverage
│   ├── iter_1_run_0.ucdb    # Individual runs
│   └── ...
└── testplan.md              # Generated test plan
```

## Supported Simulators

- **QuestaSim** - Full support with UCDB coverage
- **Verilator** - Line coverage support

## Documentation

- [QUICK_START.md](QUICK_START.md) - Installation and setup
- [ARCH.md](ARCH.md) - Architecture details
- [docs/RUN_AGENT_GUIDE.md](docs/RUN_AGENT_GUIDE.md) - Detailed usage guide
- [docs/VERILATOR_QUICKSTART.md](docs/VERILATOR_QUICKSTART.md) - Verilator setup

## Project Structure

```
LangGraph/
├── run_agent.py          # CLI entry point
├── configs/              # Example environment configs
├── src/
│   ├── config.py         # Configuration loading
│   ├── graphs/react.py   # LangGraph agent
│   ├── tools/            # Agent tools (compile, simulate, etc.)
│   ├── simulators/       # Simulator adapters
│   └── prompts/          # System prompts
└── data/                 # Design files
```
