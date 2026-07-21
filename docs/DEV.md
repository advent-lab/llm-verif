# Developer Setup and Guide

## Prerequisites

- **Python 3.8+** (tested with 3.10+)
- **QuestaSim** (e.g., Questa 23.4) or **Verilator** installed and licensed
- **OpenAI API key** (or compatible LLM provider key)
- Access to design files (RTL + spec) in the `data/` directory

## Installation

The framework uses direct imports via path manipulation -- no package installation is required.

```bash
# 1. Clone the repository
git clone <repo-url>
cd llm-verif

# 2. Create Python environment
#    On SOL/ASU cluster:
module load mamba/latest
mamba create -n lg_venv -c conda-forge pip -y
source activate lg_venv

#    Or with standard venv:
python -m venv .venv
source .venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Load simulator (SOL-specific)
module load bittware/questa-23.4
# export LM_LICENSE_FILE=<license-server>
```

### Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `langgraph` | 1.0.6 | Graph orchestration |
| `langchain` | 1.2.6 | Tool framework, message types |
| `langchain-openai` | 1.1.7 | OpenAI LLM integration |
| `tiktoken` | 0.12.0 | Token counting for context window tracking |
| `python-dotenv` | 1.2.1 | Environment file loading |
| `lcovparser` | 0.0.1 | Verilator LCOV parsing |

## Environment Setup

```bash
# Copy the example env file
cp .env.example .env

# Edit with your settings
vi .env
```

At minimum, set:
- `OPENAI_API_KEY` -- your API key
- `COMPILER` -- path to simulator binaries (e.g., `/packages/apps/fpga/Questa/questa_fe/bin`)
- `SIMULATOR` -- `questasim` or `verilator`
- `DESIGN_NAME` -- design key from `dashboard.json`
- `DASHBOARD_PATH` -- absolute path to `dashboard.json`

See [CONFIG.md](CONFIG.md) for the full configuration reference.

## Running the Agent

```bash
# Run with default .env
python run_agent.py

# Run with a specific config file
python run_agent.py -e configs/codex-vs-react.env

# Validate config without running
python run_agent.py --validate-only

# Run with verbose error output
python run_agent.py --verbose
```

There is also a simpler entry point at `src/main.py` which can be used directly:
```bash
python -m src.main
```

## Project Structure

```
llm-verif/
├── run_agent.py              # CLI entry point with logging setup
├── src/
│   ├── main.py               # Simpler entry point
│   ├── config.py             # Configuration loading and validation
│   ├── graphs/
│   │   └── react.py          # LangGraph agent (nodes, edges, routing)
│   ├── state/
│   │   └── schemas.py        # AgentState TypedDict definition
│   ├── tools/
│   │   ├── __init__.py       # Tool registry (get_all_tools, set_tool_config)
│   │   ├── filesystem.py     # read_file, write_file, list_directory
│   │   ├── simulation.py     # compile_design, run_simulation
│   │   ├── analysis.py       # parse_coverage
│   │   ├── workflow.py       # signal_done (not registered in get_all_tools)
│   │   ├── simulation_mock.py  # Mock tools for TEST_MODE
│   │   └── analysis_mock.py    # Mock tools for TEST_MODE
│   ├── simulators/
│   │   ├── base.py           # SimulatorAdapter ABC, CoverageResult
│   │   ├── questasim_adapter.py  # QuestaSim implementation
│   │   └── verilator_adapter.py  # Verilator implementation
│   ├── utils/
│   │   ├── dashboard_loader.py   # Dashboard.json design loading
│   │   ├── design_loader.py      # Module header extraction
│   │   ├── questasim.py          # QuestaSim command builders
│   │   └── tokens.py             # Token counting utilities
│   └── prompts/
│       ├── loader.py         # System prompt template loader
│       └── system.md         # System prompt template
├── scripts/
│   ├── compute_covagent.py   # events.jsonl -> tokens.json (token allocation by category)
│   ├── visualize_tokens.py   # tokens.json -> token_alloc.html (pie chart)
│   ├── make_category_csv.py # tokens.json -> by_category.csv
│   ├── gen_codex_prompt.py   # Generate prompts for Codex comparison
│   ├── test_design.py        # Scaffold compile+sim test for a dashboard design
│   ├── test_prompt_loader.py # Test prompt template loading
│   └── README.md             # Script-by-script usage reference
├── configs/                  # Example environment configs
├── data/                     # Design files (RTL + specs)
├── docs/                     # Documentation
│   ├── ARCH.md               # Architecture reference
│   ├── CONFIG.md             # Configuration reference
│   ├── DEV.md                # This file
│   ├── NOTES.md              # Technical notes and observations
│   ├── TODO.md               # Future work items
│   └── WARNINGS.md           # Known pitfalls and gotchas
└── work/                     # Run output directory (gitignored)
```

For detailed architecture information, see [ARCH.md](ARCH.md).

## Testing

### Without a Simulator (Mock Mode)

Set `TEST_MODE=1` in your `.env` to use mock simulator and coverage tools:

```bash
# In .env
TEST_MODE=1

python run_agent.py
```

This exercises the full graph without needing QuestaSim or Verilator installed.

### Testing Prompt Loading

```bash
python scripts/test_prompt_loader.py
```

## Analyzing Run Results

### Token Allocation

Use `scripts/compute_covagent.py` to turn a run's `events.jsonl` into a per-category
token breakdown (`tokens.json`), then `scripts/visualize_tokens.py` /
`scripts/make_category_csv.py` to chart or export it. See
[scripts/README.md](../scripts/README.md) and the "Reproducing Token Allocation
Results" section of the top-level [README.md](../README.md).

### Run Artifacts

After a run completes, check the work directory:

```bash
# View the run report (written by the agent during finalize)
cat work/<RUN_ID>/report.md

# View the final state
cat work/<RUN_ID>/final_state.json

# View the full agent log
less work/<RUN_ID>/run.log

# List generated testbenches
ls work/<RUN_ID>/testbenches/

# Check coverage logs
ls work/<RUN_ID>/logs/
ls work/<RUN_ID>/coverage/
```

## Debugging Tips

### Enable Debug Logging

Set `LOG_LEVEL=DEBUG` in your `.env` to see detailed API request/response logs, tool execution details, and state transitions.

Set `LOG_TRUNCATE=0` to see full (untruncated) tool call arguments and results in logs.

### Common Issues

1. **"OPENAI_API_KEY not set"**: Ensure the key is in your `.env` file or exported in your shell.

2. **"COMPILER path invalid"**: The `COMPILER` variable must point to the directory containing simulator executables (e.g., `vlog`, `vsim`), not the executable itself.

3. **"Design not found in dashboard"**: Check that `DESIGN_NAME` matches a key in `dashboard.json` and that `DASHBOARD_PATH` is an absolute path.

4. **Runs terminating early**: Check `MAX_ITERATIONS`, `MAX_NO_PROGRESS`, and `CONTEXT_WINDOW` settings. The run log shows which limit was hit.

5. **LangGraph recursion limit**: If you see recursion limit errors, increase `RECURSION_LIMIT` (default: 300). Each node visit counts as one step.

### Inspecting the Graph

```python
from src.graphs.react import create_react_graph

graph = create_react_graph()
graph.get_graph().print_ascii()
```

## Code Conventions

- **Error handling**: Tools return `{"success": False, "error": "..."}` on failure -- never raise exceptions to the LLM.
- **File paths**: Store as strings in state (for JSON serialization), use `Path` objects in implementation code.
- **Config access in tools**: Tools use module-level `_config` global set by `set_tool_config()` during initialization.
- **Logging**: Use the standard `logging` module. ANSI color codes are stripped from file logs by `_StripAnsiFilter`.
- **Naming**: Log files use `{tool}_iter_{N}.log` or `{tool}_iter_{N}_retry_{M}.log` pattern.
