# llm_verif package

Core package entry point for the CLI, environment setup, and orchestrating conversations.

- `llm_verif.llm_verif`: CLI argument parsing, logging, and wiring together environment, simulators, and LLM backends.
- `prompt_templates`, `conversation_manager`, `conversation_runner`: Prompt shaping and multi-turn control flow.
- `record`, `storage`, `environment`, `dashboard`: Persistence of run metadata, artifact layout, and dataset loading.

::: llm_verif
