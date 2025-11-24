# Conversation manager

Manages message history, truncation, and stack pointer logic for multi-turn prompting.

- Tracks system/user/assistant messages and enforces token budgets.
- Provides slice/stack-pointer handling to drop polluted context.

::: llm_verif.conversation_manager
