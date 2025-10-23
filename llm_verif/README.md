# 🧠 LLM-Driven Verilog Testbench Generation and Coverage Closure

This project leverages large language models (LLMs) to automatically generate Verilog testbenches from design specifications, iteratively refine them, and close coverage gaps using industry-standard simulators. It supports multi-turn prompting, testplan-guided generation, error recovery, and merging coverage across runs.

**Supported Simulators:**
- **Verilator** (open-source, **primary supported simulator**)
- **QuestaSim/ModelSim** (commercial, also supported)

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
| `--backend` | **[Required]** LLM backend to use (`openai` for unified async backend, `vllm` for legacy local engine) |
| `--base_url` | Base URL for OpenAI-compatible API (e.g., `http://localhost:8000/v1` for vLLM server). Defaults to OpenAI's API if not specified |
| `--api_key` | API key for authentication. Can also be set via `OPENAI_API_KEY` environment variable |
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

## 🔌 LLM Backend Configuration

### Unified OpenAI-Compatible Backend (Recommended)

The framework now uses a unified async backend that supports any OpenAI-compatible API endpoint. This provides maximum flexibility and better performance.

#### Using OpenAI's API

```bash
llm_verif \
    --backend openai \
    --dotenv_path .env \
    ...
```

Your `.env` file should contain:
```bash
OPENAI_API_KEY=sk-your-api-key-here
```

#### Using vLLM Server (Recommended for Local Models)

vLLM provides an OpenAI-compatible server for fast local inference. This is our **recommended approach** for local models.

**1. Install vLLM:**
```bash
pip install vllm
```

**2. Start vLLM server with AWQ-quantized Llama 3.3 70B (recommended):**

For 2x A100 GPUs (our typical setup):
```bash
vllm serve casperhansen/llama-3.3-70b-instruct-awq \
    --api-key your-secret-token \
    --port 8000 \
    --tensor-parallel-size 2 \
    --gpu-memory-utilization 0.85 \
    --quantization awq \
    --max-model-len 32766
```

For other GPU configurations:
- **4x GPUs**: Set `--tensor-parallel-size 4`
- **8x GPUs**: Set `--tensor-parallel-size 8`
- **Single GPU**: Set `--tensor-parallel-size 1` (may require smaller model or more aggressive quantization)

**Server Options Explained:**
- `--api-key`: Secret token for authentication (use a secure random string)
- `--port`: Server port (default: 8000)
- `--tensor-parallel-size`: Number of GPUs to use for model sharding
- `--gpu-memory-utilization`: Fraction of GPU memory to use (0.85 = 85%)
- `--quantization awq`: Use AWQ quantization (for `casperhansen` models)
- `--max-model-len`: Maximum sequence length (adjust based on available memory)

**3. Configure the framework to use your vLLM server:**
```bash
llm_verif \
    --backend openai \
    --base_url http://localhost:8000/v1 \
    --api_key your-secret-token \
    --model casperhansen/llama-3.3-70b-instruct-awq \
    --tokenizer meta-llama/Llama-3.3-70B-Instruct \
    --design /path/to/design \
    --simulator verilator \
    --compiler /path/to/verilator \
    ...
```

Or via `.env` file:
```bash
OPENAI_BASE_URL=http://localhost:8000/v1
OPENAI_API_KEY=your-secret-token
MODEL=casperhansen/llama-3.3-70b-instruct-awq
TOKENIZER=meta-llama/Llama-3.3-70B-Instruct
BACKEND=openai
```

**Benefits of vLLM Server:**
- **Fastest inference** with PagedAttention and optimized CUDA kernels
- **Better resource management** - server runs independently, can be shared across experiments
- **Standard OpenAI API** - same code works with OpenAI, vLLM, or any compatible server
- **Production-ready** with async support and batching
- **AWQ quantization** - 4-bit quantization for 70B models on consumer GPUs

**Verifying Server is Running:**
```bash
curl http://localhost:8000/v1/models
```

Should return a list of available models.

#### Using Other OpenAI-Compatible Servers

The unified backend works with any OpenAI-compatible endpoint:

**Local LLaMA.cpp server:**
```bash
--backend openai --base_url http://localhost:8080/v1
```

**Ollama:**
```bash
--backend openai --base_url http://localhost:11434/v1
```

**Custom inference servers:**
```bash
--backend openai --base_url https://your-server.com/v1
```

### Legacy vLLM Backend (Deprecated)

The legacy `--backend vllm` option loads models in-process using vLLM. This is **deprecated** in favor of the unified async backend with vLLM server:

```bash
# Legacy approach (not recommended)
llm_verif --backend vllm --model /path/to/model ...
```

**Why migrate?**
- Legacy backend loads model in the same process (uses more memory)
- No async support (blocking I/O)
- Server approach allows better resource sharing and management
- Standard API makes it easy to switch between providers

**Migration:** Switch to `--backend openai` with `--base_url` pointing to your vLLM server.

### Running vLLM Experiments on SLURM Clusters

For SLURM-based HPC environments, use `scripts/run_vllm_design.sh` which automates vLLM server setup and experiment execution.

**Key Features:**
- Automatically starts vLLM server with your GPU configuration
- Creates standalone vLLM virtual environment (avoids dependency conflicts with llm_verif)
- Manages server lifecycle (startup, health checks, graceful shutdown)
- Processes multiple designs and configurations in batch

**Quick Start:**

1. **Generate config files** (creates `.env` files in `configs/`):
   ```bash
   bash scripts/setup_vllm_configs.sh
   ```
   **Important:** Ensure `BASE_URL=http://localhost:8000/v1` (use `http://`, not `https://`)

2. **Edit script configuration** (`scripts/run_vllm_design.sh`):
   - Set `designs` array (which hardware modules to test)
   - Set `base_envs` array (which config files to use)
   - Adjust `TENSOR_PARALLEL_SIZE` to match GPU count

3. **Submit job**:
   ```bash
   sbatch scripts/run_vllm_design.sh
   ```

**SLURM Resource Settings:**
- Default: 2x A100 GPUs, 64GB RAM, 12 hours
- Modify `#SBATCH` directives in script header as needed
- Match `TENSOR_PARALLEL_SIZE` variable to GPU count

**Script Workflow:**
1. Creates standalone `vllm-venv/` (isolated from llm_verif dependencies)
2. Starts vLLM server on `http://localhost:8000/v1` with API key `test-key`
3. Waits for server readiness (max 5 minutes)
4. Creates llm_verif `venv/` and installs framework
5. Runs experiments for each design/config combination
6. Stops vLLM server and copies results to permanent storage

**Troubleshooting:**
- **vLLM fails to start**: Check `$SCRATCH_DIR/vllm_server.log`
- **HTTPS/SSL errors**: Verify configs use `http://` not `https://`
- **GPU OOM**: Reduce `--gpu-memory-utilization` or use smaller model
- **Results location**: `results/vllm_run_${SLURM_JOB_ID}/`

---

## 🔁 Iterative Coverage Closure

Each run:
1. Loads design spec and module header from the dashboard configuration.
2. Generates testbenches using the configured LLM backend.
3. Simulates via Verilator (or QuestaSim) and measures statement coverage.
4. If coverage is below 100%, it prompts the LLM to improve coverage using:
   - Missed lines in coverage reports (from LCOV for Verilator or UCDB for QuestaSim)
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
- **Coverage Reports**:
  - **Verilator** (primary):
    - `.dat` coverage database files
    - `coverage.info` LCOV format files
    - `coverage.txt` human-readable coverage reports
  - **QuestaSim** (also supported):
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

### Unified OpenAI-Compatible Backend
- **Async-first architecture**: New unified async backend supporting any OpenAI-compatible API
- **vLLM server integration**: Recommended approach for local models with fast inference
- **AWQ quantization support**: Run 70B models on consumer GPUs with 4-bit quantization
- **Flexible endpoints**: Works with OpenAI, vLLM, LLaMA.cpp, Ollama, and custom servers
- **Legacy backend deprecated**: `--backend vllm` replaced by `--backend openai` with `--base_url`
- **Better resource management**: Server runs independently, can be shared across experiments

### Verilator as Primary Simulator
- **Full Verilator support**: Open-source simulator, now the primary supported option
- **LCOV parser** (`lcovparser.py`): Parses Verilator's LCOV coverage output
- **Coverage merging**: Supports merging `.dat` files across batches and runs
- **Unified interface**: Same CLI and workflow for both Verilator and QuestaSim
- **QuestaSim still supported**: Commercial simulator remains available as an alternative

### Logging Improvements
- Converted all `print()` statements to proper logging calls
- Configurable verbosity with `-v` and `-vv` flags
- Better debugging and production deployment support

### Configuration
- Enhanced `.env` file support for all configuration options
- Flexible CLI argument precedence over environment variables
- Required vs. optional argument validation
