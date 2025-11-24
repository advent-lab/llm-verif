# Developer Guide

This guide is for contributors who want to understand how the LLM verification stack is put together, how to run it locally, and where to plug in new features.

## Local development setup
- Requirements: Python 3.11+, Verilator or QuestaSim installed, and access to an OpenAI-compatible endpoint (API key or vLLM server).
- Create an environment:
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  pip install -e .
  # or use the helper to mirror CI defaults
  bash build_llm_venv.sh
  ```
- Editable installs expose the CLI as `llm_verif`. Keep datasets under `data/` and point the CLI to one design directory at a time.
- Environment config is merged from CLI flags and your `.env`. Required values are `design`, `compiler`, `id`, `simulator`, and `backend`. Typical `.env` keys:
  ```
  OPENAI_API_KEY=...
  DESIGN=/abs/path/to/data/<design>
  COMPILER=/path/to/verilator
  SIMULATOR=verilator
  BACKEND=openai
  ID=local-dev
  ```

## How the pieces fit together
- Entry point: `llm_verif/llm_verif.py` parses args + `.env`, sets logging, and instantiates the pipeline.
- Environment and data loading: `Environment` loads `dashboard.json` to find spec, design, and context files, extracts the Verilog module header, and wires a `FileStore` for artifacts.
- Conversation orchestration: `ConversationRunner` creates a `ConversationManager` with the system prompt (from `prompt_templates.py`), calls the LLM backend for batches, parses JSON responses, and selects the best testbench by simulated coverage.
- LLM backends: `ModelChat` is the abstraction; `OpenAIBackend` is the recommended async path for OpenAI/vLLM-compatible servers. `llama3_chat.py` is the legacy in-process backend.
- Simulation layer: `Simulator` defines the interface. `verilator.py` and `questasim.py` compile, run, and parse coverage (LCOV via `lcovparser.py`). Cross-run merging is handled through the simulator’s `merge_and_parse_cross_run_coverage`.
- Bookkeeping: `Record` writes per-iteration metrics to CSV; `storage.py` manages work/output directories; `vector_store.py` handles retrieval for prompts when enabled.

## Running the pipeline locally
Minimal end-to-end run (Verilator):
```bash
llm_verif \
  --dotenv_path .env \
  --backend openai \
  --simulator verilator \
  --design /abs/path/to/data/sha1_core \
  --compiler /path/to/verilator \
  --id dev01 \
  --runs 1 \
  --work_dir ./work \
  -v
```
- For a vLLM server, point `--base_url http://localhost:8000/v1` and set `--api_key` (or via `.env`).
- Outputs land under `--work_dir` and the `output/` subdir, with CSV summaries named per design and timestamp.
- Use `--testplan/--no_design_prompt/--temperature_function/...` to tune behaviour; defaults aim for iterative coverage closure with merging enabled.

## Testing and validation
- Fast checks: `pytest tests/test_json_parsing.py tests/regex_tests.py -q`
- Full suite: `pytest tests -q` (some tests require simulator binaries and dataset paths; keep `design` and `compiler` paths valid).
- When touching coverage or simulator logic, re-run `tests/verilator_tests.py` with an available Verilator install.
- Add focused tests for new prompt-parsing logic or simulator responses to avoid regressions.

## Debugging tips
- Increase verbosity with `-v/ -vv` to see prompt, response, and coverage summaries.
- Logs and generated testbenches live under `work/<design>/`; inspect `tb_llm_<design>_*` and simulator transcripts to reproduce issues.
- The `ConversationManager` enforces a token budget (`--max_context_tokens`); if prompts truncate, raise this value or adjust retrieval.

## Extending the system
- New simulator: subclass `Simulator` (see `verilator.py`) and implement compile/run/coverage hooks plus `merge_and_parse_cross_run_coverage`.
- New LLM backend: subclass `ModelChat`, implement async `generate_response_async`, and make sure JSON formatting follows `ModelChat.convert_json_response_to_dict`.
- New dataset entries: update `dashboard.json` with `spec`, `design`, and `design_context` paths; keep paths absolute or use `$(BASE_DIR)` placeholders consistently.
- Prompts: edit `prompt_templates.py` and add tests for any new JSON contract or parsing expectations.

## API docs (MkDocs)
- Deps: `pip install mkdocs mkdocs-material mkdocstrings[python]`
- Serve locally: `mkdocs serve` (browse http://127.0.0.1:8000). Build static site: `mkdocs build` (outputs `site/`, already gitignored).
- Reference pages live in `docs/reference/` and are driven by mkdocstrings; update nav in `mkdocs.yml` if you add modules.

## Pull request checklist
- Tests relevant to the change pass locally.
- Docs updated (README and this guide) when flags, prompts, or interfaces change.
- No generated artifacts or large data files are committed.
