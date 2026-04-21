# Quick Start Guide

## 1 — One-Time Environment Setup

```bash
# Load modules (SOL cluster)
module load mamba/latest
module load bittware/questa-23.4

# Activate Python environment
source activate lg_venv

# Navigate to framework directory
cd /path/to/llm-verif

# Install dependencies (first time only)
pip install -r requirements.txt
```

---

## 2 — Configure sol.env

Open `sol.env` and fill in the required values:

```
OPENAI_API_KEY=sk-...your-key-here...

DESIGN_NAME=cvdp_agentic_alu       # must match a key in dashboard.json
DASHBOARD_PATH=/absolute/path/to/dashboard.json
BASE_DIR=/absolute/path/to/data    # root that dashboard.json variables expand from

COMPILER=/absolute/path/to/questasim/bin
LM_LICENSE_FILE=your-license-string
SIMULATOR=questasim

WORK_DIR=./work/my_run_1           # change this for every run
RUN_ID=my_run_1
```

Everything else in `sol.env` has sensible defaults.

---

## 3 — Validate Before Running

```bash
python run_agent.py -e sol.env --validate-only
```

Fix any reported missing variables or paths before proceeding.

---

## 4 — Choose a Mode and Architecture

### Code Coverage Mode

No extra variables needed — this is the default.

| Architecture | `ARCHITECTURE` value | Description |
|---|---|---|
| v1 | `v1` | Single ReAct agent — simplest |
| v2.1 | `v2.1` | Orchestrator + Analyzer-Generator + CRT agents |
| v2 | `v2` | Orchestrator + persistent Design Expert + Test Generators |

Set `ARCHITECTURE` (and optionally per-role model overrides) in `sol.env`, then:

```bash
python run_agent.py -e sol.env
```

**Example — v1:**
```
ARCHITECTURE=v1
MODEL=gpt-4o
WORK_DIR=./work/alu_v1_codecov
RUN_ID=alu_v1_codecov
```

**Example — v2.1:**
```
ARCHITECTURE=v2.1
ORCHESTRATOR_MODEL=gpt-4o
ANALYZER_GENERATOR_MODEL=gpt-4o
CRT_MODEL=gpt-4o-mini
WORK_DIR=./work/alu_v21_codecov
RUN_ID=alu_v21_codecov
```

**Example — v2:**
```
ARCHITECTURE=v2
ORCHESTRATOR_MODEL=gpt-4o
DESIGN_EXPERT_MODEL=gpt-4o
TEST_GENERATOR_MODEL=gpt-4o-mini
WORK_DIR=./work/alu_v2_codecov
RUN_ID=alu_v2_codecov
```

---

### Functional Coverage Mode

**Step A — Prepare your testbench template**

Your template must be a complete, compilable SystemVerilog file (`module tb_llm ... endmodule`) containing:
- DUT instantiation
- Clock generation
- Covergroups and bins (defined by you)
- Coverage sampling logic
- A stimulus placeholder delimited by these exact comments:

```systemverilog
    // STIMULUS_BEGIN
    initial begin
        $finish;
    end
    // STIMULUS_END
```

The framework finds these markers, replaces the block with the agent's generated stimulus wrapped in `initial begin ... $finish; end`, and compiles the result. The rest of your template is never modified.

**Minimal template example:**
```systemverilog
`timescale 1ns/1ps

module tb_llm;
    logic clk;
    logic [3:0] opcode;
    logic signed [31:0] operand1, operand2, result;

    my_dut dut (.opcode(opcode), .operand1(operand1),
                .operand2(operand2), .result(result));

    initial clk = 0;
    always #5 clk = ~clk;

    covergroup cg_ops @(posedge clk);
        cp_opcode: coverpoint opcode {
            bins add = {4'h0};
            bins sub = {4'h1};
            // ... your bins ...
        }
    endgroup
    cg_ops cg_inst = new();

    // STIMULUS_BEGIN
    initial begin
        $finish;
    end
    // STIMULUS_END

endmodule
```

**Step B — Add to sol.env:**

```
FUNCTIONAL_COVERAGE_ENABLED=1
FUNCTIONAL_COVERAGE_TARGET=100.0        # stop when this % of bins are hit
FUNCTIONAL_COVERAGE_TESTBENCH=/absolute/path/to/your/tb_funcov.sv
```

> If `dashboard.json` already has a `"verif"` key for your design pointing to the template, `FUNCTIONAL_COVERAGE_TESTBENCH` is not needed — it is loaded automatically.

**Step C — Set architecture and run:**

Same `ARCHITECTURE` options as code coverage. Example for v2.1:

```
ARCHITECTURE=v2.1
FUNCTIONAL_COVERAGE_ENABLED=1
FUNCTIONAL_COVERAGE_TARGET=100.0
FUNCTIONAL_COVERAGE_TESTBENCH=/absolute/path/to/tb_funcov.sv
ORCHESTRATOR_MODEL=gpt-4o
ANALYZER_GENERATOR_MODEL=gpt-4o
CRT_MODEL=gpt-4o-mini
WORK_DIR=./work/alu_v21_funcov
RUN_ID=alu_v21_funcov
```

```bash
python run_agent.py -e sol.env
```

---

## 5 — Output Structure

After a run, `WORK_DIR/RUN_ID/` contains:

**v1 (single-agent):**
```
work/my_run/
├── testbenches/
│   ├── tb_iter_1.sv              # generated testbench
│   ├── tb_iter_1_injected.sv     # patched template (funcov mode only)
│   └── ...
├── logs/
│   ├── compile_iter_1.log
│   ├── sim_iter_1.log
│   └── ...
├── coverage/
│   ├── iter_1.ucdb               # per-iteration coverage DB
│   ├── cumulative.ucdb           # merged code coverage
│   └── cumulative_funcov.ucdb    # merged functional coverage (funcov mode only)
├── testplan.md
├── report.md
├── run.log                       # full console log
├── events.jsonl                  # structured event stream (one JSON object per line)
└── final_state.json
```

**v2 / v2.1 (multi-agent) — additional per-generator artifacts:**
```
work/my_run/
├── testbenches/
│   ├── tb_iter_1_gen_0.sv        # generator 0's testbench
│   ├── tb_iter_1_gen_1.sv        # generator 1's testbench (parallel)
│   └── ...
├── logs/
│   ├── compile_iter_1_gen_0.log
│   ├── sim_iter_1_gen_0.log
│   ├── crt_iter_1_gen_1.log      # per-generator conversation log (v2.1)
│   └── ...
├── coverage/
│   ├── cov_iter_1_gen_0.ucdb     # per-generator coverage DB
│   ├── cov_iter_1_gen_1.ucdb
│   ├── cumulative.ucdb
│   └── cumulative_funcov.ucdb    # (funcov mode only)
├── sim_work/
│   ├── gen_0/                    # isolated QuestaSim work library per generator
│   └── gen_1/
├── testplan.md
├── report.md
├── run.log
├── events.jsonl
└── final_state.json
```

---

## 6 — Project Structure

```
llm-verif/
├── run_agent.py                        # Main CLI entry point
├── run_batch.py                        # Batch runner (multiple designs sequentially)
├── run_agent_design_batch.py           # Per-design batch runner
├── sol.env                             # Environment config (edit this)
├── dashboard.json                      # Design inventory (maps names → RTL/spec paths)
├── requirements.txt
│
├── src/
│   ├── config.py                       # Loads all env vars, resolves paths, validates
│   ├── main.py                         # Legacy/alternative entry point
│   │
│   ├── graphs/                         # LangGraph state machine definitions
│   │   ├── react.py                    # v1 — single ReAct agent loop
│   │   ├── orc_exp_gen.py              # v2 — Orchestrator + Design Expert + Test Generators
│   │   ├── ag_crt.py                   # v2.1 — Orchestrator + Analyzer-Generator + CRT
│   │   └── agents/                     # Subagent implementations (v2 / v2.1)
│   │       ├── design_expert.py        # v2 persistent Design Expert
│   │       ├── orchestrator.py         # v2 orchestrator tool definitions
│   │       ├── test_generator.py       # v2 stateless Test Generator
│   │       ├── analyzer_generator.py   # v2.1 Analyzer-Generator (reads RTL, targeted)
│   │       ├── crt_agent.py            # v2.1 CRT agent (broad randomized stimulus)
│   │       └── ag_crt_orchestrator.py  # v2.1 orchestrator tool definitions
│   │
│   ├── state/
│   │   └── schemas.py                  # AgentState (v1) and MultiAgentState (v2/v2.1)
│   │
│   ├── tools/                          # LangChain tools exposed to agents
│   │   ├── __init__.py                 # Tool registry — selects tools by mode
│   │   ├── filesystem.py               # read_file, write_file, list_directory
│   │   ├── simulation.py               # compile_design, run_simulation
│   │   ├── analysis.py                 # parse_coverage, parse_functional_coverage
│   │   ├── workflow.py                 # run_verification_cycle (composite)
│   │   ├── coverage.py                 # get_coverage_status
│   │   ├── simulation_mock.py          # Mock simulator (TEST_MODE=1)
│   │   └── analysis_mock.py            # Mock analysis (TEST_MODE=1)
│   │
│   ├── simulators/                     # Adapter pattern for simulator backends
│   │   ├── base.py                     # Abstract SimulatorAdapter interface
│   │   ├── questasim_adapter.py        # QuestaSim (Siemens/Mentor) — full support
│   │   └── verilator_adapter.py        # Verilator — code coverage only
│   │
│   ├── prompts/                        # System prompt templates (markdown)
│   │   ├── loader.py                   # Loads and interpolates prompt templates
│   │   ├── system.md                   # v1 code coverage prompt
│   │   ├── system_functional.md        # v1 functional coverage prompt
│   │   ├── orchestrator_system.md      # v2 orchestrator prompt
│   │   ├── expert_system.md            # v2 Design Expert prompt
│   │   ├── generator_system.md         # v2 Test Generator prompt
│   │   ├── ag_crt_orchestrator_system.md  # v2.1 orchestrator prompt
│   │   ├── analyzer_generator_system.md   # v2.1 Analyzer-Generator prompt
│   │   └── crt_system.md               # v2.1 CRT prompt
│   │
│   └── utils/
│       ├── questasim.py                # vlog/vsim command builders + stimulus injection
│       ├── design_loader.py            # Extracts module headers from RTL
│       ├── dashboard_loader.py         # Resolves design paths from dashboard.json
│       ├── event_log.py                # Structured JSONL event logging (events.jsonl)
│       ├── agent_logging.py            # Colored console + file logging
│       ├── conversation_logger.py      # Per-agent conversation turn logging
│       ├── tokens.py                   # Token counting helpers
│       └── token_tracking.py           # Token usage aggregation across agents
│
├── data/                               # Hardware designs (RTL + specs + funcov templates)
├── docs/
│   ├── ARCH.md                         # Architecture deep-dive
│   ├── CONFIG.md                       # Full env var reference
│   └── guides/
│       └── opentitan_design_guide.md
├── scripts/                            # Log parsing, batch analysis, test utilities
└── work/                               # Run outputs — created at runtime, gitignored
```

---

## 7 — Common Issues

| Error | Fix |
|---|---|
| `FileNotFoundError: Environment file not found` | Run from the `llm-verif/` repo root (where `run_agent.py` lives) |
| `Missing required environment variables` | Fill in `COMPILER`, `SIMULATOR`, `DESIGN_NAME`, `DASHBOARD_PATH` in sol.env |
| `FUNCTIONAL_COVERAGE_ENABLED=1 requires a testbench template` | Add `FUNCTIONAL_COVERAGE_TESTBENCH=...` to sol.env |
| `Template '...' is missing // STIMULUS_BEGIN ... // STIMULUS_END markers` | Add the marker comments to your template's empty initial block |
| Coverage stuck at 0% | Check `logs/compile_iter_1.log` — testbench likely failed to compile |
| Simulation timeout | Increase `SIM_TIMEOUT` in sol.env (default: 60s) |
| `LM_LICENSE_FILE` error | Ensure the value in sol.env matches your QuestaSim license setup |
