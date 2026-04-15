# Implementation Notes

Caveats, design rationale, and non-obvious implementation details.

## v2 Multi-Agent Architecture

### `create_agent` API Choice

The v2 agents use `create_agent` from `langchain.agents` (newer API) rather than `create_react_agent` from `langgraph.prebuilt`. This API supports `system_prompt` and `middleware` parameters directly, and returns a compiled graph suitable for both standalone invocation and sub-graph embedding.

### Expert Context Growth

The Design Expert uses `MemorySaver` for persistence, meaning its message history grows monotonically across all queries within a run. On large designs with many iterations, the expert's context can approach model limits. The `EXPERT_CONTEXT_LIMIT` config provides a soft cap — the expert returns a warning when approaching this limit, but does not automatically truncate its history.

**Mitigation**: For long runs on large designs, consider using a model with a large context window for the expert, or limiting the number of expert queries per iteration.

### Generator Tool Isolation via Closures

Each test generator gets its own tool instances created via closures in `make_generator_tools()`. This avoids shared mutable state between concurrent generators. Each closure captures:
- A generator-specific `sim_work/gen_{id}/` directory
- Its own `QuestasimAdapter` instance
- Its own retry counter state

This is intentional — the alternative (shared tools with locking) would be more complex and error-prone.

### Coverage Cache Architecture

The shared `get_coverage_status` tool reads from a module-level `_coverage_cache` dict that is updated by `update_state_node` after each coverage merge. This is a deliberate coupling — the cache must be updated in the parent graph's update node, not by the agents themselves, to ensure consistency.

### Token Tracking `agent` Field

The `build_token_record()` function accepts an `agent` parameter (default `"react"` for v1 backward compatibility). In v2, records are tagged as `"orchestrator"`, `"design_expert"`, or `"test_generator"` to enable per-agent cost analysis.

### Module Registry

`extract_module_headers_per_module()` in `design_loader.py` extracts headers for ALL modules in each RTL file, not just the top-level module. This builds the `module_registry` dict used by the orchestrator to dispatch unit-level generators. The registry maps `module_name -> header_string`.

### v1 Untouched

The v2 implementation does not modify any v1 code paths. `AgentState`, `create_react_graph()`, and the v1 tool registry (`tools/__init__.py`) are unchanged. Architecture selection happens at the entry point (`run_agent.py` / `main.py`) based on `config.architecture`.
