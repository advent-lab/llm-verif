# Spec2Cov

LLM-powered automated hardware verification using LangGraph. The agent reads design specifications, generates SystemVerilog testbenches or UVM sequences, runs simulations, and iteratively improves coverage across three verification modes: code coverage, functional coverage, and UVM-based functional coverage.

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

## Verification Modes

### Mode A: Code Coverage (Default)

The LLM generates complete SystemVerilog testbenches from scratch. Coverage is measured at the RTL statement/branch/condition/expression/toggle level.

```env
# No extra variables needed — this is the default
FUNCTIONAL_COVERAGE_ENABLED=0
```

### Mode B: Functional Coverage

The LLM generates stimulus-only code that fills a user-provided testbench template. The template defines the module, signals, DUT, covergroups, and `// BEGIN_STIMULUS` / `// END_STIMULUS` markers. The LLM writes only between those markers.

```env
FUNCTIONAL_COVERAGE_ENABLED=1
FUNCTIONAL_COVERAGE_TESTBENCH=path/to/template.sv
FUNCTIONAL_COVERAGE_TARGET=100.0   # Optional, default 100
```

### Mode C: Combined Coverage (Two-Phase)

Phase 1 runs code coverage (full testbenches). When it plateaus or completes, the framework automatically transitions to Phase 2 (functional coverage) using the same run directory.

```env
COMBINED_COVERAGE_ENABLED=1
FUNCTIONAL_COVERAGE_TESTBENCH=path/to/template.sv
```

### UVM Mode

UVM is an orthogonal modifier that can be applied on top of the functional coverage mode. Instead of raw testbenches, the LLM generates UVM sequence classes and a UVM test class each iteration. The fixed testbench infrastructure (driver, monitor, agent, env, interface) is user-provided and never modified by the LLM (except the driver, which requires an explicit `request_infra_modification` call).

```env
UVM_ENABLED=1
UVM_FILELIST=path/to/filelist.f
UVM_SEQUENCE_FILE=my_seq.sv
UVM_TOP_MODULE=my_top
UVM_TEST_NAME=my_test
UVM_HOME=/opt/siemens/questasim/uvm-1.2     # Optional
UVM_SEQ_ITEM_FILE=path/to/seq_item.sv        # Optional, injected into prompt
UVM_COVERAGE_MODULE_FILE=path/to/tb_llm.sv  # Optional, injected into prompt
UVM_COVERAGE_MODE=functional                 # "functional" (default) or "line"
```

## Configuration

Create a `.env` file or use configs from `configs/`. See [docs/CONFIG.md](docs/CONFIG.md) for the full variable reference.

### Required

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `COMPILER` | Path to simulator binaries directory |
| `SIMULATOR` | `questasim` or `verilator` |
| `DESIGN_NAME` | Design name (must exist in dashboard) |
| `DASHBOARD_PATH` | Path to dashboard.json |

### Common Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL` | `gpt-4o` | LLM model |
| `WORK_DIR` | `./work` | Output directory |
| `RUN_ID` | `default_run` | Run identifier |
| `MAX_ITERATIONS` | `10` | Max LLM API calls |
| `MAX_NO_PROGRESS` | `5` | Stop after N iterations without coverage improvement |
| `SIM_RUNS` | `5` | Simulation runs per testbench (different seeds) |
| `NUM_FEEDBACK_HOLES` | `3` | Priority coverage holes shown in feedback (0 = none) |
| `CONTEXT_WINDOW` | `128000` | Max tokens before terminating run |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Output

All artifacts are saved to `{WORK_DIR}/{RUN_ID}/`. Combined mode uses phase subdirectories.

```
work/my_run/
├── testbenches/           # Generated testbenches or sequence/test files
│   ├── tb_iter_1.sv
│   └── ...
├── logs/
│   ├── compile_iter_1.log
│   ├── sim_iter_1.log
│   └── ...
├── coverage/
│   ├── cumulative.ucdb    # Merged coverage across all iterations
│   ├── sim_run_1.ucdb
│   └── ...
├── iterations/            # Per-iteration snapshots (UVM mode)
│   ├── iter_1/
│   └── ...
└── testplan.md            # Generated test plan (if TESTPLAN=1)

# Combined mode:
work/my_run/
├── code_cov/              # Phase 1 artifacts
└── func_cov/              # Phase 2 artifacts
```

## Supported Simulators

- **QuestaSim** — Full support: UCDB code coverage, functional coverage bins, UVM 3-step compile flow
- **Verilator** — Line coverage support

## Documentation

- [QUICK_START.md](QUICK_START.md) — Installation and setup
- [docs/ARCH.md](docs/ARCH.md) — Architecture and pipeline details
- [docs/CONFIG.md](docs/CONFIG.md) — Full configuration reference
- [docs/FRAMEWORK_REPORT.md](docs/FRAMEWORK_REPORT.md) — Detailed UVM integration report

## Project Structure

```
llm-verif/
├── run_agent.py              # CLI entry point
├── configs/                  # Example environment configs
├── src/
│   ├── config.py             # Configuration loading and validation
│   ├── graphs/react.py       # LangGraph agent and routing logic
│   ├── state/schemas.py      # AgentState definition
│   ├── tools/                # Agent tools (compile, simulate, analyze, etc.)
│   ├── simulators/           # QuestaSim and Verilator adapter pattern
│   ├── validators/           # UVM pre/post-compile validation
│   ├── utils/                # Token counting, design loading, coverage utils
│   └── prompts/              # System prompt template and loader
└── data/                     # Design examples with specs, RTL, and UVM testbenches
```
