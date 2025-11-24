# Conversation runner

Orchestrates prompt generation, LLM calls, coverage evaluation, and selection of best testbenches per iteration.

- Parses JSON responses, evaluates coverage via simulator, and records metrics.
- Builds `ConversationManager` with prompt templates and handles batch processing.

::: llm_verif.conversation_runner
