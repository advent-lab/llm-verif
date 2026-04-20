# Run Guide — Spec2Cov (Plug and Play)

Everything runs through `run_agent.py` using `sol.env` as the config file.
All commands are run from the `Z_New_Arch/` directory.

---

## Step 1 — One-Time Environment Setup

Do this once per machine / session.

```bash
# Load modules (SOL cluster)
module load mamba/latest
module load bittware/questa-23.4

# Activate Python environment
source activate lg_venv

# Navigate to framework directory
cd /path/to/Z_New_Arch
```

---

## Step 2 — Fill in sol.env (Required Every Time)

Open `sol.env` and set these values. Everything else can stay at its default.

```
# ── YOUR API KEY ─────────────────────────────────────────────
OPENAI_API_KEY=sk-...your-key-here...

# ── DESIGN ───────────────────────────────────────────────────
DESIGN_NAME=cvdp_agentic_alu          # must match the key in dashboard.json

# ── PATHS (use absolute paths) ───────────────────────────────
DASHBOARD_PATH=/absolute/path/to/dashboard.json
BASE_DIR=/absolute/path/to/data       # root that dashboard.json variables expand from

# ── SIMULATOR ────────────────────────────────────────────────
COMPILER=/absolute/path/to/questasim/bin
LM_LICENSE_FILE=your-license-string
SIMULATOR=questasim

# ── WORK DIRECTORY ───────────────────────────────────────────
# Change this for every run to keep outputs separate
WORK_DIR=./work/alu_run_1
RUN_ID=alu_run_1
```

> **Tip:** Keep a separate copy of `sol.env` for each design you test regularly.

---

## Step 3 — Validate Before Running

Always run this first to catch missing paths or typos before spending API credits.

```bash
python run_agent.py -e sol.env --validate-only
```

Expected output:
```
 Loaded environment from: .../sol.env
 Configuration valid
```

If it prints a missing variable or path error, fix `sol.env` and re-validate.

---

## Code Coverage Mode

In `sol.env`, make sure these lines are **absent or commented out**:
```
# FUNCTIONAL_COVERAGE_ENABLED=1    ← must be commented or absent
# FUNCTIONAL_COVERAGE_TESTBENCH=   ← must be commented or absent
```

Then pick your architecture and run.

---

### Code Coverage — v1 (Single ReAct Agent)

**When to use:** Simplest. One agent reads RTL, writes testbenches, compiles, and simulates in a loop.

In `sol.env`, set:
```
ARCHITECTURE=v1
MODEL=gpt-4o
WORK_DIR=./work/alu_v1_codecov
RUN_ID=alu_v1_codecov
```

Run:
```bash
python run_agent.py -e sol.env
```

---

### Code Coverage — v2.1 (Orchestrator → Analyzer-Generator + CRT)

**When to use:** Better coverage on complex designs. Orchestrator plans strategy, dispatches CRT agents for broad sweeps and Analyzer-Generator agents for targeted holes.

In `sol.env`, set:
```
ARCHITECTURE=v2.1
MODEL=gpt-4o                          # fallback model
ORCHESTRATOR_MODEL=gpt-4o
ANALYZER_GENERATOR_MODEL=gpt-4o
CRT_MODEL=gpt-4o-mini
WORK_DIR=./work/alu_v21_codecov
RUN_ID=alu_v21_codecov
```

Run:
```bash
python run_agent.py -e sol.env
```

---

### Code Coverage — v2 (Orchestrator-Expert-Generator)

**When to use:** The orchestrator delegates all RTL analysis to a persistent Design Expert agent that remembers everything it has read. Good for large designs with many submodules.

In `sol.env`, set:
```
ARCHITECTURE=v2
MODEL=gpt-4o                          # fallback model
ORCHESTRATOR_MODEL=gpt-4o
DESIGN_EXPERT_MODEL=gpt-4o
TEST_GENERATOR_MODEL=gpt-4o-mini
WORK_DIR=./work/alu_v2_codecov
RUN_ID=alu_v2_codecov
```

Run:
```bash
python run_agent.py -e sol.env
```

---

## Functional Coverage Mode

### Before Running — Prepare Your Testbench Template

Your functional coverage testbench file must:
- Be a complete, compilable SystemVerilog file (with `` `timescale ``, `module tb_llm`, `endmodule`)
- Contain the DUT instantiation, clock generation, covergroups, and coverage sampling logic
- Have a **stimulus placeholder region** delimited by exactly these comments:

```systemverilog
    // STIMULUS_BEGIN
    initial begin
        $finish;
    end
    // STIMULUS_END
```

The framework finds `// STIMULUS_BEGIN` and `// STIMULUS_END`, replaces everything between them with the agent's generated body lines wrapped in `initial begin ... $finish; end`, and compiles the result. The agent never touches the rest of the template.

**Minimal template structure:**
```systemverilog
`timescale 1ns/1ps

module tb_llm;
    // --- Signals ---
    logic clk;
    logic [3:0] opcode;
    // ... other ports ...

    // --- DUT ---
    my_dut dut (.clk(clk), .opcode(opcode), ...);

    // --- Clock ---
    initial clk = 0;
    always #5 clk = ~clk;

    // --- Covergroups ---
    covergroup cg_ops @(posedge clk);
        cp_opcode: coverpoint opcode { bins add = {4'h0}; ... }
    endgroup
    cg_ops cg_inst = new();

    // --- Stimulus (filled in by agent each iteration) ---
    // STIMULUS_BEGIN
    initial begin
        $finish;
    end
    // STIMULUS_END

endmodule
```

**Add your file path to `sol.env`:**
```
FUNCTIONAL_COVERAGE_TESTBENCH=/absolute/path/to/your/alu_funcov_tb.sv
```

> **Note:** If `dashboard.json` already has a `"verif"` key for your design pointing to the testbench template, you do not need `FUNCTIONAL_COVERAGE_TESTBENCH` — it is loaded automatically.

---

### Functional Coverage — v1 (Single ReAct Agent)

In `sol.env`, set:
```
ARCHITECTURE=v1
MODEL=gpt-4o
FUNCTIONAL_COVERAGE_ENABLED=1
FUNCTIONAL_COVERAGE_TARGET=100.0      # stop when this % of bins are hit
FUNCTIONAL_COVERAGE_TESTBENCH=/absolute/path/to/alu_funcov_tb.sv
WORK_DIR=./work/alu_v1_funcov
RUN_ID=alu_v1_funcov
```

Run:
```bash
python run_agent.py -e sol.env
```

---

### Functional Coverage — v2.1 (Orchestrator → Analyzer-Generator + CRT)

In `sol.env`, set:
```
ARCHITECTURE=v2.1
MODEL=gpt-4o
ORCHESTRATOR_MODEL=gpt-4o
ANALYZER_GENERATOR_MODEL=gpt-4o
CRT_MODEL=gpt-4o-mini
FUNCTIONAL_COVERAGE_ENABLED=1
FUNCTIONAL_COVERAGE_TARGET=100.0
FUNCTIONAL_COVERAGE_TESTBENCH=/absolute/path/to/alu_funcov_tb.sv
WORK_DIR=./work/alu_v21_funcov
RUN_ID=alu_v21_funcov
```

Run:
```bash
python run_agent.py -e sol.env
```

---

### Functional Coverage — v2 (Orchestrator-Expert-Generator)

In `sol.env`, set:
```
ARCHITECTURE=v2
MODEL=gpt-4o
ORCHESTRATOR_MODEL=gpt-4o
DESIGN_EXPERT_MODEL=gpt-4o
TEST_GENERATOR_MODEL=gpt-4o-mini
FUNCTIONAL_COVERAGE_ENABLED=1
FUNCTIONAL_COVERAGE_TARGET=100.0
FUNCTIONAL_COVERAGE_TESTBENCH=/absolute/path/to/alu_funcov_tb.sv
WORK_DIR=./work/alu_v2_funcov
RUN_ID=alu_v2_funcov
```

Run:
```bash
python run_agent.py -e sol.env
```

---

## Output Structure

After a run, `WORK_DIR` contains:

```
work/alu_v1_codecov/
├── testbenches/          # generated testbench .sv files
│   ├── tb_iter_1.sv
│   ├── tb_iter_2.sv
│   └── ...
├── logs/                 # compile and simulation logs per iteration
│   ├── compile_iter_1.log
│   ├── sim_iter_1.log
│   └── ...
├── coverage/             # UCDB files and coverage reports
│   ├── iter_1.ucdb
│   ├── cumulative.ucdb          # code coverage: merged across all iterations
│   └── cumulative_funcov.ucdb   # functional coverage: merged (funcov mode only)
├── testplan.md           # agent's verification plan
├── notes.md              # agent's iteration notes
├── report.md             # final report (written at termination)
├── run.log               # full console log saved to file
└── final_state.json      # machine-readable final state
```

---

## Quick Reference — What to Change Per Run

| What you want | Lines to change in sol.env |
|---|---|
| Different design | `DESIGN_NAME`, `WORK_DIR`, `RUN_ID` |
| Different architecture | `ARCHITECTURE`, model lines |
| Switch to functional coverage | Add `FUNCTIONAL_COVERAGE_ENABLED=1`, `FUNCTIONAL_COVERAGE_TESTBENCH=` |
| Switch back to code coverage | Comment out or remove those two lines |
| Longer run | Increase `MAX_ITERATIONS`, `MAX_NO_PROGRESS` |
| Faster (fewer API calls) | Decrease `MAX_ITERATIONS`, `SIM_RUNS` |
| Cheaper model | Set `MODEL=gpt-4o-mini` (and per-agent model overrides) |

---

## Common Issues

**`FileNotFoundError: Environment file not found`**
→ Run from the `Z_New_Arch/` directory, not a subdirectory.

**`ValueError: FUNCTIONAL_COVERAGE_ENABLED=1 requires a testbench template`**
→ Add `FUNCTIONAL_COVERAGE_TESTBENCH=/absolute/path/to/your/tb.sv` to `sol.env`.

**`ValueError: Template '...' is missing // STIMULUS_BEGIN ... // STIMULUS_END markers`**
→ Your testbench template must contain these two comment markers to delimit the empty stimulus placeholder. See the template structure above.

**`Testbench not found` during compile**
→ The agent wrote to a path it cannot find. Check that `WORK_DIR` is writable.

**Simulation timeout immediately**
→ `SIM_TIMEOUT` is too short. Default is 60s. Set `SIM_TIMEOUT=120` or higher.

**Coverage stuck at 0%**
→ Check `work/WORK_DIR/logs/compile_iter_1.log` — the testbench likely failed to compile.

**`LM_LICENSE_FILE` error from QuestaSim**
→ Make sure `LM_LICENSE_FILE` in `sol.env` matches what `module load` sets up.
