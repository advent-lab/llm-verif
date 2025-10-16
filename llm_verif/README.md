# 🧠 LLM-Driven Verilog Testbench Generation and Coverage Closure

This project leverages large language models (LLMs) to automatically generate Verilog testbenches from design specifications, iteratively refine them, and close coverage gaps using industry-standard simulators. It supports multi-turn prompting, testplan-guided generation, error recovery, and merging coverage across runs.

**Supported Simulators:**
- **Verilator** (open-source)
- **QuestaSim/ModelSim** (commercial)

---

## 🗂️ Project Structure

```
llm_verif_dataset/
├── build_llm_venv.sh             # Helper script to build environment
├── CONTRIBUTING.md               # Instructions on contributing
├── dashboard.json                # Dataset configuration file
├── dashboard_scripts/            # Helper scripts for dataset management
├── data/                         # Dataset directory
├── llm_verif/
│   ├── __init__.py               # Package initialization
│   ├── chatgpt_chat.py           # ChatGPT API implementation (extends ModelChat)
│   ├── conversation_manager.py   # Manages conversation history and context
│   ├── conversation_runner.py    # Orchestrates testbench generation workflow
│   ├── dashboard.py              # Dataset management and loading
│   ├── environment.py            # Environment configuration and design specs
│   ├── lcovparser.py             # LCOV coverage report parser (for Verilator)
│   ├── llama3_chat.py            # Local Llama model implementation (extends ModelChat)
│   ├── llm_verif.py              # Main CLI entry point
│   ├── metrics.py                # Coverage metrics and analysis
│   ├── modelchat.py              # Abstract base class for LLM backends
│   ├── prompt_templates.py       # Prompt templates for testbench generation
│   ├── questasim.py              # QuestaSim simulator implementation (extends Simulator)
│   ├── record.py                 # Records and tracks evaluation metrics
│   ├── simulator.py              # Abstract base class for simulators
│   ├── storage.py                # File storage manager for artifacts
│   ├── util.py                   # Utility functions
│   ├── vector_store.py           # Vector store for RAG (document retrieval)
│   └── verilator.py              # Verilator simulator implementation (extends Simulator)
├── pyproject.toml                # Python project configuration
├── README.md                     # Main project documentation
├── requirements.in               # Direct dependencies
├── requirements.txt              # Pinned dependencies
├── scripts/                      # Helper scripts
└── tests/                        # Test suite
```
---

## 🚀 Quickstart

### 1. 📁 Prepare Design Data

Each design should be registered in a `dashboard.json` with the following structure:

```json
{
  "chacha_top": {
    "spec": ["$(BASE_DIR)/spec/chacha_spec.txt"],
    "design": ["$(BASE_DIR)/rtl/chacha.v"],
    "design_context": ["$(BASE_DIR)/rtl/constants.v"]
  }
}
```

Replace `$(BASE_DIR)` with the folder containing your dataset. The testbench generator will parse specs and design headers to guide generation.

---

### 2. ⚙️ Environment Setup

Install CLI tool:
```bash
pip install -e llm_verif/
```
---

### 3. 🧪 Running Evaluation

Run the main evaluation script:

```bash
llm_verif \
    --dotenv_path .env \
    --backend openai \
    --simulator verilator \
    --design /path/to/design \
    --compiler /path/to/verilator \
    --runs 5 \
    --testplan \
    --merge-coverage \
    --temperature 0.3 \
    --temperature_function "logarithmic" \
    --batch_size 3 \
    --max_iterations 12 \
    --max_valid_iter 8 \
    --sim_runs 20 \
    --output ./logs \
    -v  # Verbose output (use -vv for debug)
```

#### Arguments:
| Argument | Description |
|----------|-------------|
| `--dotenv_path` | **[Required]** Path to dotenv file containing API keys and configuration |
| `--backend` | **[Required]** LLM backend to use (`openai` or `vllm`) |
| `--simulator` | **[Required]** Simulator to use (`verilator` or `questasim`) |
| `--design, -d` | **[Required]** Path to the design directory |
| `--compiler, -c` | **[Required]** Path to simulator compiler (e.g., Verilator or QuestaSim) |
| `--id` | **[Required]** User-specified identifier for the run |
| `--runs, -r` | Number of independent testbench generation runs (default: 1) |
| `--work_dir, -w` | Working directory for testbenches and logs (default: ./work) |
| `--output, -o` | Output directory for log files (default: output) |
| `--testplan` | Enable 2-stage generation: verification plan then testbench (default: true) |
| `--crt` | Enable constrained random testing (default: true) |
| `--merge-coverage, -m` | Merge coverage reports into final report (default: true) |
| `--temperature, -t` | Sampling temperature (default: 0.3) |
| `--temperature_function` | Temperature function: `constant`, `logarithmic`, `capped_sigmoid` (default: constant) |
| `--batch_size, -b` | Number of testbenches generated per prompt (default: 1) |
| `--max_iterations` | Maximum number of iterations per run (default: 5) |
| `--max_valid_iter` | Maximum number of successful iterations per run (default: 3) |
| `--sim_runs` | Number of times to simulate constrained random testbenches (default: 20) |
| `--no_sampling` | Disable LLM response sampling (default: false) |
| `--seed, -S` | Random seed for reproducibility |
| `--remove_polluted_context` | Enable removal of polluted context from conversation history (default: false) |
| `--no_design_prompt` | Disable design prompt injection (default: false) |
| `--zero_shot` | Enable zero-shot prompting (default: false) |
| `--quantize, -q` | Enable model quantization (default: false) |
| `--model` | LLM model name or path (default: gpt-4o) |
| `--tokenizer` | Tokenizer for ConversationManager (default: meta-llama/Llama-3.3-70B-Instruct) |
| `-v, -vv` | Increase verbosity: `-v` = INFO, `-vv` = DEBUG |
---

## 🔁 Iterative Coverage Closure

Each run:
1. Loads design spec and module header from the dashboard configuration.
2. Generates testbenches using the configured LLM backend.
3. Simulates via Verilator or QuestaSim and measures statement coverage.
4. If coverage is below 100%, it prompts the LLM to improve coverage using:
   - Missed lines in coverage reports (from LCOV or UCDB)
   - Targeted design unit suggestions
   - Error messages from compilation or simulation failures
5. Optionally merges coverage reports across batches and runs.

---

## 📊 Output Files

- **CSV Logs**: `<design>_evaluation_<timestamp>.csv` contains metrics per iteration:
  - Pass/fail status, error codes
  - Statement coverage percentage
  - Token counts and generation time
  - Temperature and sampling parameters
  - Run and iteration metadata
- **Testbenches**: Stored in the output dir with pattern:
  ```
  tb_llm_<design>_<run>_<iter>_<batch>.v
  ```
- **Coverage Reports** (Verilator):
  - `.dat` coverage database files
  - `coverage.info` LCOV format files
  - `coverage.txt` human-readable coverage reports
- **Coverage Reports** (QuestaSim):
  - `.ucdb` Unified Coverage Database files
  - `.txt` human-readable coverage reports
  - `merged_coverage_<design>.ucdb` if merging is enabled

---

## 🧪 CoverageResponse Error Codes

| Code | Meaning |
|------|---------|
| 0    | Success |
| 1    | Compile Error |
| 2    | Simulation Error |
| 3    | Timeout |
| 4    | JSON Decode Error |
| 5    | Missing `$finish` in testbench |

---

## 🧠 Prompt Types

- `system_prompt`: System prompt for each iteration
- `m1_prompt`: Generic prompt with module header and specification 
- `m2_prompts`: Returns a prompt for generating a testplan and an m1_prompt
- `m3_prompt`: Directs LLM to either fix an error or improve coverage
- `error_prompt`: Fixes based on simulation/compile errors
- `design_prompt`: Injects full design for later rounds

---

## 📤 Logging and Storage

All generated files are stored in the `FileStore` directory specified via `--output`. The framework preserves:
- Generated testbenches (.v files)
- Compilation logs (_compile.log)
- Simulation logs (_sim.log)
- Coverage reports (.txt, .ucdb, .dat, .info files)
- CSV evaluation metrics

### Logging Levels

The tool uses Python's logging framework with the following verbosity levels:
- **No flag**: WARNING level - only warnings and errors
- **`-v`**: INFO level - operational information and progress
- **`-vv`**: DEBUG level - detailed debugging information including prompts and responses

All print statements have been converted to appropriate logging calls for better control and filtering.

---

## 🧪 Testing and Debugging Tips

- Run with `--batch_size 1` for isolated debugging of single testbenches
- Use `-vv` for debug-level logging to see full prompts and LLM responses
- Check specific logs for failures:
  - `<testbench>_compile.log` - compilation errors
  - `<testbench>_sim.log` - simulation runtime errors
  - `<testbench>_report.txt` - coverage analysis
- The `design_prompt()` function injects full RTL context mid-run for better context
- Set `--seed` for reproducible generations
- Use `--max_iterations` and `--max_valid_iter` to control run length during testing

---

## 🆕 Recent Updates

### Verilator Integration
- **Full Verilator support**: Open-source alternative to commercial simulators
- **LCOV parser** (`lcovparser.py`): Parses Verilator's LCOV coverage output
- **Coverage merging**: Supports merging `.dat` files across batches and runs
- **Unified interface**: Same CLI and workflow for both Verilator and QuestaSim

### Logging Improvements
- Converted all `print()` statements to proper logging calls
- Configurable verbosity with `-v` and `-vv` flags
- Better debugging and production deployment support

### Configuration
- Enhanced `.env` file support for all configuration options
- Flexible CLI argument precedence over environment variables
- Required vs. optional argument validation
