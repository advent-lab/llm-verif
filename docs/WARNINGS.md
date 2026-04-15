# WARNINGS

Use this file to record risks, environment pitfalls, and operational gotchas.

## Conventions
- Describe the symptom, likely cause, and safe workaround.
- Include platform details (Windows/Linux), tool versions, and repro steps when possible.
- Keep secrets out of this file.

## Entries

### Unit-Level UCDB Merge Needs Empirical Validation

**Symptom**: When merging coverage databases from unit-level generators (targeting submodules) with top-level generators, the resulting cumulative coverage may have unexpected values or double-counting.

**Cause**: QuestaSim's `vcover merge` merges by design unit (module) name. Unit-level tests produce coverage for the target submodule only, while top-level tests produce coverage for all modules. The merge behavior when combining these has not been extensively tested.

**Workaround**: Start with top-level-only verification (`target_module="top"`) and add unit-level targeting incrementally. Monitor cumulative coverage for unexpected jumps or drops after unit-level merges.

### Parallel QuestaSim Work Library Isolation

**Symptom**: Compilation or simulation errors when multiple generators run concurrently, with messages about locked files or corrupt work libraries.

**Cause**: Each generator creates its own QuestaSim work library at `sim_work/gen_{id}/work/`. If the filesystem doesn't support concurrent writes to the same parent directory, or if QuestaSim has undocumented locking behavior, conflicts may occur.

**Workaround**: If concurrent generator failures occur, reduce `MAX_GEN_PER_ITER=1` to serialize generator execution. The `gen_{id}` directories should still provide isolation in most cases.

### Expert Context Degradation Over Long Runs

**Symptom**: Design Expert responses become less accurate or miss details after many queries (10+ iterations with multiple expert queries each).

**Cause**: The expert's `MemorySaver` checkpointer accumulates all messages, including tool results with large file contents. As context fills, the model may lose track of earlier information or hit context window limits.

**Workaround**: Set `EXPERT_CONTEXT_LIMIT` to a value below your model's context window (e.g., 100000 for a 128K model). Use a large-context model for the expert. Consider reducing the number of expert queries per iteration in the orchestrator prompt.

### Generator Recursion Limit

**Symptom**: Generator fails with a LangGraph recursion limit error despite having retries remaining.

**Cause**: The generator's recursion limit is computed as `max(50, gen_max_retries * 10 + 20)`. Each retry cycle (think + write + think + compile + think + sim) consumes ~6 graph steps. If the model takes extra reasoning steps, the limit may be hit.

**Workaround**: Increase `GEN_MAX_RETRIES` (which also increases the recursion limit) or reduce generator prompt complexity to minimize reasoning steps.
