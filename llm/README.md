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

├── build_llm_venv.sh                 # Python environment build script
├── evaluations                      
│   ├── evaluate_chatgpt-4o.py        # Script for running a chatgpt-4o eval
│   └── evaluate_methodology6.py      # Script for running a Llama3.3 eval
├── README.md
├── requirements.in
├── requirements.txt
├── scripts/                          # Scripts for running various configurations/jobs
├── src
│   ├── chatgpt_chat.py               # Extension of ModelChat for ChatGPT-4o
│   ├── conversation_manager.py       # Class used for controlling the conversation flow
│   ├── dashboard.py                  # Loads designs and their data from the dataset
│   ├── environment.py                # Stores environment data
│   ├── eval_runs_util.py             # Utils for evaluation runs (now mainly data management)
│   ├── evaluation.py                 # Util function for evaluating metrics (deprecating soon)
│   ├── __init__.py                   
│   ├── llama3_chat.py                # Extension of ModelChat for Llama3.3
│   ├── modelchat.py                  # Base class for models
│   ├── ollama_chat.py                # Extension of ModelChat
│   ├── prompt_templates.py           # Templates for prompts used during conversations
│   ├── quantize_llama3.3.py          # Script for quantization
│   ├── questasim.py                  # Extention of Simulator for QuestaSim (needs refactor)
│   ├── simulator.py                  # Base class for integrating simulators
│   ├── storage.py                    # Stores conversation artifacts
│   └── vector_store.py               
└── tests/                            # Tests for framework
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
---

### 3. 🧪 Running Evaluation

Run the main evaluation script:

```bash
python evaluate_methodology6.py \
    --design /path/to/design \
    --compiler /path/to/questasim \
    --generations 5 \
    --testplan \
    --merge-coverage \
    --temperature 0.3 \
    --temperature_function "logarithmic" \
    --batch_size 3 \
    --max_iterations 12 \
    --max_valid_iter 8 \
    --output ./logs
```

#### Arguments:
| Argument | Description |
|----------|-------------|
| `--design, -d` | Path to the design directory |
| `--compiler, -c` | Path to QuestaSim installation |
| `--generations, -g` | Number of independent testbench generation runs |
| `--testplan` | Enable 2-stage generation: verification plan then testbench |
| `--merge-coverage, -m` | Merge UCDBs into final report |
| `--temperature, -t` | Sampling temperature |
| `--temperature_function` | One of: `constant`, `logarithmic`, `capped_sigmoid` |
| `--batch_size, -b` | Number of testbenches generated per prompt |
| `--output, -o` | Directory to store logs and testbenches |
| `--no_sampling` | Forces no logit sampling |
| `--seed, -S` | Sets seed for generation |
| `--remove_polluted_context` | Enables removing polluted context |
| `--max_iterations` | Sets the max number of iterations per run |
| `--max_valid_iterations` | Sets the max number of valid iterations per run |
| `--id` | Sets the id for the run |
| `--quantize, -q` | Set this flag if a quantized model is being used |
| `--tokenizer` | Path to tokenizer if a separate tokenizer is used |
| `--dotenv_path` | Path to dotenv config used for API models |
---

## 🔁 Iterative Coverage Closure

Each run:
1. Loads design spec and module header.
2. Generates testbenches using LLM.
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

- `system_prompt`: System prompt for each iteration
- `m1_prompt`: Generic prompt with module header and specification 
- `m2_prompts`: Returns a prompt for generating a testplan and an m1_prompt
- `m3_prompt`: Directs LLM to either fix an error or improve coverage
- `error_prompt`: Fixes based on simulation/compile errors
- `design_prompt`: Injects full design for later rounds

---

## 📤 Logging and Storage

All generated files are moved to the `FileStore` directory specified via `--output`. The framework preserves:
- Testbenches
- Compile/simulation logs
- Coverage files

---

## 🧪 Testing and Debugging Tips

- Run with `--batch_size 1` for isolated debugging
- Check logs: `_compile.log`, `_sim.log`, `_report.txt`
- Use `design_prompt()` to insert entire RTL context mid-run
