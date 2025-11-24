# ModelChat base

Abstract interface for LLM backends plus JSON parsing helpers.

- Defines `generate_response_async` contract and temperature/top-p configuration.
- Provides `convert_json_response_to_dict` used by conversation runner.

::: llm_verif.modelchat
