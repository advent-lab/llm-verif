# Environment

Runtime environment assembly: pulls design assets from the dataset, extracts module headers, and configures storage paths.

- Resolves specs/design files, prepares prompt snippets, and builds `FileStore`/CSV paths.
- Exposes design metadata (name, module header, spec text) used by conversations and simulators.

::: llm_verif.environment
