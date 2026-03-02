
# Configuration (Environment Variables)

This workflow is configured via a `.env` file (or any `KEY=VALUE` env file passed to the runner). Most settings map directly to fields in `src/config.py` and control design selection, simulator invocation, and iteration limits.

See `.env.example` for a complete annotated template.

## LLM

| Variable | Required | Default | Description |
|---|---:|---|---|
| `OPENAI_API_KEY` | Yes* | — | API key for the LLM provider used by the agent. *If `TEST_MODE=1`, this can be omitted because simulator + analysis tools are mocked.* |
| `MODEL` | No | `gpt-4o` | Chat model name passed to the LLM client (e.g., `gpt-4o-mini`). Use a model that supports tool calling well. |
| `TEMPERATURE` | No | `0.4` | Sampling temperature for the agent LLM; higher values increase randomness and exploration. |
| `MAX_TOKENS` | No | `4096` | Maximum output tokens for a single LLM response (affects cost and response length). |

## Design Selection

You must configure *either* Dashboard mode (recommended) or Direct mode.

| Variable | Required | Default | Description |
|---|---:|---|---|
| `DESIGN_NAME` | Yes** | — | Design key/name to load from `DASHBOARD_PATH` in Dashboard mode. **Required by `run_agent.py` validation; also used for logging and run labeling.** |
| `DASHBOARD_PATH` | Yes** | — | Path to `dashboard.json` used to resolve the design's spec/RTL/context files in Dashboard mode. **Required by `run_agent.py` validation.** |
| `BASE_DIR` | No | `DASHBOARD_PATH/../data/` | Base directory for resolving `$(BASE_DIR)` references inside `dashboard.json`. If omitted, defaults to `DASHBOARD_PATH`'s parent `data/` directory. |
| `DESIGN` | No | — | Direct path to a design directory (must contain `docs/` and `rtl/`) for ad-hoc runs without a dashboard; used only if Dashboard mode isn't configured. |
| `DESIGN_CONTEXT` | No | `1` | Enables RTL/context access via tools when set to `1`; when `0`, the agent can still read the spec but must not read RTL through the filesystem tool. |

## Paths / Outputs

| Variable | Required | Default | Description |
|---|---:|---|---|
| `RUN_ID` | No | `default_run` | Identifier for a run; used to create an isolated output directory under `WORK_DIR` (e.g., `work/<RUN_ID>/`). |
| `WORK_DIR` | No | `./work` | Base directory where run artifacts are written (testbenches, logs, coverage DBs). The effective run directory is `WORK_DIR/RUN_ID`. |

## Simulator

| Variable | Required | Default | Description |
|---|---:|---|---|
| `SIMULATOR` | Yes** | `questasim` | Simulator backend selector (currently `questasim` or `verilator`). **Required by `run_agent.py` validation.** |
| `COMPILER` | Yes** | — | Path to the simulator *bin directory* (e.g., contains `vlog`, `vsim`, `vcover` for QuestaSim). **Required by `run_agent.py` validation (and validated at runtime unless `TEST_MODE=1`).** |
| `LM_LICENSE_FILE` | No | — | License configuration commonly required by QuestaSim; passed through via the environment to the simulator processes (not parsed by Python). |

## Workflow Limits

| Variable | Required | Default | Description |
|---|---:|---|---|
| `MAX_ITERATIONS` | No | `10` | Maximum number of API calls before stopping (caps the agent loop). Also used as max coverage iterations. |
| `MAX_RETRIES` | No | `3` | Maximum consecutive failures (compile/sim) before terminating the run. |
| `MAX_NO_PROGRESS` | No | `5` | Maximum consecutive iterations with no cumulative coverage improvement before routing to finalize (prevents infinite "stuck" loops). |
| `SIM_RUNS` | No | `5` | Number of simulation runs (seeds) per generated testbench; higher values can improve coverage at the cost of runtime. |
| `SIM_TIMEOUT` | No | `60` | Per-simulation timeout in seconds (used to kill/abort long or stuck simulations). Also used as compilation timeout. |
| `TESTPLAN` | No | `1` | Enables testplan generation when set to `1`; when `0`, the agent skips writing a testplan and goes directly to testbench generation. |
| `NUM_FEEDBACK_HOLES` | No | `0` | Priority coverage holes included in feedback after `parse_coverage`. `0` = unbounded/all holes shown. Set to a positive integer to cap output and save tokens. |
| `COVERAGE_HOLE_RADIUS` | No | `5` | Number of context lines shown above and below each uncovered line in coverage feedback. Range: 1-20 (clamped). |
| `CONTEXT_WINDOW` | No | `128000` | Maximum token count before the agent terminates the run. Should match or stay below the model's actual context window to prevent API errors. |
| `RECURSION_LIMIT` | No | `300` | LangGraph graph recursion limit. Each node visit counts as one step. Increase for runs with many iterations. |

## Logging / Debug

| Variable | Required | Default | Description |
|---|---:|---|---|
| `LOG_LEVEL` | No | `INFO` | Python logging verbosity (e.g., `DEBUG`, `INFO`, `WARNING`); controls console + file log detail. |
| `LOG_TRUNCATE` | No | `1` | When set to `1`, truncates long tool-call results and arguments in log output; set to `0` to see full content. |
| `TEST_MODE` | No | `0` | When set to `1`, uses mock simulator/coverage tools so the graph can be exercised without an installed simulator; also relaxes certain validations (e.g., `OPENAI_API_KEY`). |

## Configuration Precedence

1. Environment variables set before running the script
2. Values loaded from the `.env` file (or file specified via `--env-file`)
3. Defaults defined in `src/config.py`

When using `run_agent.py --env-file`, the specified file is loaded with `override=True`, meaning its values overwrite any previously set environment variables.
