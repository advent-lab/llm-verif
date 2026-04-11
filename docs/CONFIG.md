
# Configuration (Environment Variables)

This workflow is configured via a `.env` file (or any `KEY=VALUE` env file passed to the runner). All settings map to fields in `src/config.py`. Pass a custom file with `python run_agent.py -e path/to/file.env`.

---

## LLM

| Variable | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `OPENAI_API_KEY` | Yes* | — | API key for the LLM provider. *Omit only when `TEST_MODE=1`.* |
| `MODEL` | No | `gpt-4o` | Chat model name passed to the LLM client. Use a model with strong tool-calling support. |
| `TEMPERATURE` | No | `0.4` | Sampling temperature. Lower values (0.2–0.4) give more deterministic code generation. |
| `MAX_TOKENS` | No | `4096` | Maximum output tokens per LLM response. |

---

## Design Selection

Configure either Dashboard mode (recommended) or Direct mode.

| Variable | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `DESIGN_NAME` | Yes** | — | Design key to load from `DASHBOARD_PATH`. Also used for logging and run labeling. |
| `DASHBOARD_PATH` | Yes** | — | Path to `dashboard.json` that maps design names to spec/RTL/context files. |
| `BASE_DIR` | No | parent of `DASHBOARD_PATH` | Base directory for resolving `$(BASE_DIR)` references inside `dashboard.json`. |
| `DESIGN` | No | — | Direct path to a design directory (must contain `docs/` and `rtl/`). Used only if Dashboard mode is not configured. |
| `DESIGN_CONTEXT` | No | `1` | When `1`, the agent can read RTL files via `read_file`. When `0`, RTL access is blocked (spec-only). |

---

## Paths / Outputs

| Variable | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `RUN_ID` | No | `default_run` | Identifier for this run. Creates an isolated output directory: `WORK_DIR/RUN_ID/`. |
| `WORK_DIR` | No | `./work` | Base directory for all run artifacts (testbenches, logs, coverage DBs). |

---

## Simulator

| Variable | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `SIMULATOR` | Yes** | — | Simulator backend: `questasim` or `verilator`. |
| `COMPILER` | Yes** | — | Path to the simulator *bin directory* (e.g., the directory containing `vlog`, `vsim`, `vcover`). |
| `LM_LICENSE_FILE` | No | — | QuestaSim license file or server (e.g., `1234@license-server`). Passed through to simulator processes. |

---

## Workflow Limits

| Variable | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `MAX_ITERATIONS` | No | `10` | Maximum number of LLM API calls before stopping. |
| `MAX_RETRIES` | No | `3` | Maximum consecutive compile or sim failures before terminating. |
| `MAX_NO_PROGRESS` | No | `5` | Maximum consecutive iterations with no cumulative coverage improvement before stopping. |
| `SIM_RUNS` | No | `5` | Number of simulation runs (seeds) per generated testbench. More runs = better random coverage. |
| `SIM_TIMEOUT` | No | `60` | Per-simulation timeout in seconds. Timed-out runs are skipped; the tool continues with remaining runs. |
| `TESTPLAN` | No | `1` | When `1`, the agent generates a test plan before writing testbenches. When `0`, skips directly to generation. |
| `NUM_FEEDBACK_HOLES` | No | `3` | Number of priority uncovered lines or bins shown to the agent after coverage analysis. `0` = none. Higher values give more context but cost more tokens. |
| `CONTEXT_WINDOW` | No | `128000` | Maximum message history token count before the run terminates. Set to match or stay below your model's actual context window. |
| `READ_FILE_TOKEN_LIMIT` | No | `16000` | Maximum characters returned by `read_file`. Files larger than this are truncated with a warning. `0` = unlimited. |

---

## Code Coverage Mode (Default)

Code coverage mode is active when neither functional coverage nor combined coverage is enabled. The LLM generates complete SystemVerilog testbenches and coverage is measured at the RTL line/branch level. No extra variables are required.

```env
# Explicitly disable functional coverage (this is the default)
FUNCTIONAL_COVERAGE_ENABLED=0
```

---

## Functional Coverage Mode

In functional coverage mode the LLM generates stimulus-only code. A user-provided testbench template defines the module, DUT, covergroups, and `// BEGIN_STIMULUS` / `// END_STIMULUS` markers. The LLM fills only the space between those markers.

| Variable | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `FUNCTIONAL_COVERAGE_ENABLED` | Yes (for this mode) | `0` | Set to `1` to enable functional coverage mode. |
| `FUNCTIONAL_COVERAGE_TESTBENCH` | Yes (for this mode) | — | Absolute path to the testbench template containing `// BEGIN_STIMULUS` and `// END_STIMULUS` markers. |
| `FUNCTIONAL_COVERAGE_TARGET` | No | `100.0` | Target functional coverage percentage. The agent signals done when cumulative coverage reaches this value. |

---

## Combined Coverage Mode

Combined mode runs code coverage first (Phase 1), then automatically transitions to functional coverage (Phase 2) using the same `RUN_ID`. Work directories are split: `work/<RUN_ID>/code_cov/` and `work/<RUN_ID>/func_cov/`. The functional coverage testbench is validated at startup even though Phase 2 has not started yet.

| Variable | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `COMBINED_COVERAGE_ENABLED` | Yes (for this mode) | `0` | Set to `1` to enable the two-phase combined run. |
| `FUNCTIONAL_COVERAGE_TESTBENCH` | Yes (for this mode) | — | Path to the Phase 2 functional coverage testbench template. Required upfront even though Phase 2 starts later. |
| `FUNCTIONAL_COVERAGE_TARGET` | No | `100.0` | Target functional coverage percentage for Phase 2. |

---

## UVM Mode

UVM mode is an orthogonal modifier. It changes how files are compiled, how simulation is invoked, and what the LLM generates. It can be combined with functional coverage or combined coverage modes. When enabled it automatically activates functional coverage internally.

The LLM generates two files each iteration: a sequence file (UVM sequence classes) and a test file (UVM test class). All other testbench infrastructure (driver, monitor, agent, env, interface, scoreboard, top module, passive coverage module) is user-provided and never modified by the LLM — unless the driver is unlocked via `request_infra_modification`.

### Core UVM Variables

| Variable | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `UVM_ENABLED` | Yes (for this mode) | `0` | Set to `1` to enable UVM mode. |
| `UVM_FILELIST` | Yes | — | Path to `.f` file listing all UVM source files. Relative paths inside the file are resolved relative to the filelist's directory. Sequence and test file entries are automatically redirected to `work_dir/testbenches/`. |
| `UVM_SEQUENCE_FILE` | Yes | — | Filename (not path) of the sequence file the LLM generates each iteration (e.g., `alu_core_seq.sv`). |
| `UVM_TOP_MODULE` | Yes | — | Top-level test module name used by `vsim` (e.g., `alu_core_Top`). |
| `UVM_TEST_NAME` | Yes | — | UVM test class name passed as `+UVM_TESTNAME=<value>` to vsim (e.g., `alu_core_test`). Must match the class name the LLM generates. |

### UVM Environment Variables

| Variable | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `UVM_HOME` | No | `/opt/siemens/questasim/uvm-1.2` | Root directory of the UVM 1.2 installation. Must contain `src/uvm_pkg.sv`. |
| `UVM_TESTBENCH_DIR` | No | — | Directory containing the UVM testbench components. Used for context and file discovery. |
| `UVM_DPI_LIB` | No | — | Path to the UVM DPI shared library (e.g., `.../uvm-1.2/linux_x86_64/uvm_dpi`). Loaded by `vsim` at runtime. |

### UVM Context Variables (Injected into LLM Prompt)

| Variable | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `UVM_SEQ_ITEM_FILE` | No | — | Path to the sequence item file (e.g., `alu_core_seq_item.sv`). Contents are read and injected into the system prompt so the LLM knows the available transaction fields and constraints. |
| `UVM_COVERAGE_MODULE_FILE` | No | — | Path to the passive coverage module (e.g., `tb_llm.sv`) that defines covergroups and bins. Contents are read and injected into the system prompt so the LLM knows exactly which bins to target. |

### UVM Coverage Mode

| Variable | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `UVM_COVERAGE_MODE` | No | `functional` | Coverage reporting mode for UVM runs. `functional` uses `parse_functional_coverage` (reports uncovered bins). `line` uses `parse_coverage` (reports uncovered RTL lines with annotated source). |

---

## Logging / Debug

| Variable | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `LOG_LEVEL` | No | `INFO` | Python logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `LOG_TRUNCATE` | No | `1` | When `1`, truncates long tool-call results in log output. Set to `0` to see full content. |
| `TEST_MODE` | No | `0` | When `1`, uses mock simulator/coverage tools so the graph can be exercised without an installed simulator. Also relaxes `OPENAI_API_KEY` requirement. |
