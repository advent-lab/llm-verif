# 🧠 LLM-Driven Verilog Testbench Generation and Coverage Closure

This project leverages large language models (LLMs) to automatically generate Verilog testbenches from design specifications, iteratively refine them, and close coverage gaps using QuestaSim. It supports multi-turn prompting, testplan-guided generation, error recovery, and merging coverage across runs.

---

## 🗂️ Project Structure

```
├── evaluate_methodology6.py        # Main script to generate testbenches and close coverage
├── src/
│   ├── llama3_chat.py              # vLLM wrapper for Meta Llama 3.1-70B-Instruct
│   ├── ollama_chat.py             # Ollama API wrapper for LLM response generation
│   ├── modelchat.py                # Abstract base class for all model interfaces
│   ├── prompt_templates.py        # Multi-stage prompt generators
│   ├── questasim.py               # QuestaSim wrapper to compile/simulate/report coverage
│   ├── simulator.py               # Base simulator class with unified CoverageResponse interface
│   ├── environment.py             # Environment abstraction for dataset, design files, and setup
│   ├── eval_runs_util.py          # Utilities to record run results and export CSVs
│   ├── evaluation.py              # Evaluation metrics like pass@k
│   ├── dashboard.py               # Loads design metadata and specification from dashboard.json
│   ├── storage.py                 # Manages testbench and log storage
│   └── __init__.py
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

Install dependencies:
```bash
pip install -r requirements.txt
```

Requirements include:
- `transformers`
- `vllm`
- `torch`
- `pandas`, `numpy`
- QuestaSim (for simulation and coverage)

Ensure QuestaSim is accessible and its path is provided at runtime.

---

### 3. 🧪 Running Evaluation

Run the main evaluation script:

```bash
python evaluate_methodology6.py \
    --design ./designs/chacha_top \
    --compiler /path/to/questasim \
    --generations 5 \
    --testplan \
    --merge-coverage \
    --temperature 0.3 \
    --temperature_function logarithmic \
    --batch_size 3 \
    --max_iterations 12 \
    --max_valid_iter 8 \
    --output ./logs
```

#### Arguments:
| Argument | Description |
|----------|-------------|
| `--design` | Path to the design directory |
| `--compiler` | Path to QuestaSim installation |
| `--generations` | Number of independent testbench generation runs |
| `--testplan` | Enable 2-stage generation: verification plan then testbench |
| `--merge-coverage` | Merge UCDBs into final report |
| `--temperature` | Sampling temperature |
| `--temperature_function` | One of: `constant`, `logarithmic`, `capped_sigmoid` |
| `--batch_size` | Number of testbenches generated per prompt |
| `--output` | Directory to store logs and testbenches |

---

## 🔁 Iterative Coverage Closure

Each run:
1. Loads design spec and module header.
2. Generates testbenches using LLM (`m1_prompt` or `m2_prompts`).
3. Simulates via QuestaSim and measures statement coverage.
4. If coverage is below 100%, it prompts the LLM to improve coverage using:
   - Missed lines in coverage reports
   - Targeted design unit suggestions
5. Optionally merges UCDBs across batches and runs.

---

## 📊 Output Files

- **CSV Logs**: `<design>_evaluation6_<timestamp>.csv` contains metrics per iteration:
  - Pass/fail, error codes
  - Coverage percentage
  - Token counts and generation time
- **Testbenches**: Stored in the output dir with pattern:
  ```
  tb_llm_<design>_<run>_<iter>_<batch>.v
  ```
- **Coverage Reports**:
  - `.ucdb` and `.txt` report per testbench
  - `merged_coverage_<design>.ucdb` and report if merging is enabled

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

- `m1_prompt`: Direct testbench generation from spec + header
- `m2_prompts`: Two-stage plan + testbench
- `m3_prompt`: Coverage-based refinement prompt
- `error_prompt`: Fixes based on simulation/compile errors
- `design_prompt`: Injects full design for later rounds

---

## 🛠️ Extensions

- Support for Ollama API (`ollama_chat.py`)
- Support for PDF specs (TODO in `environment.py`)
- Batch generation and parallel coverage simulation
- LLM memory limiting (`limit_conversation`)
- Supports vLLM and Transformers APIs

---

## 🧪 Evaluation Metrics

Implemented in `evaluation.py`:
- `pass@k`: Standard probabilistic metric for multiple generations
- Max/avg coverage tracking in `Record` class

---

## 📤 Logging and Storage

All generated files are moved to the `FileStore` directory specified via `--output`. The framework preserves:
- Testbenches
- Compile/simulation logs
- Coverage files

---

## 🧪 Testing and Debugging Tips

- Run with `--batch_size 1` for isolated debugging
- Use `--remove_polluted_context` to reset LLM state
- Check logs: `_compile.log`, `_sim.log`, `_report.txt`
- Use `design_prompt()` to insert entire RTL context mid-run
