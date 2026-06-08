# AGENTS.md — implementation guide

You are implementing CovAgent, an LLM-driven hardware verification framework. The design phase is complete. Your job is to translate the design documents under [.claude/plans/](.claude/plans/) into working Python code. Read the relevant design doc before touching a subsystem; do not improvise architecture.

## What CovAgent does

A coverage-driven verification orchestrator. Given a design (RTL + spec) and a coverage goal, it:
1. Builds a structured **testplan** (testpoints, covergroups, coverpoints, bins) from the spec.
2. Spawns **persistent generator agents** — one per feature scope (e.g. CSR, ALU pipeline). Each owns its own work directory and accumulates SystemVerilog testbench files across many invocations.
3. An **orchestrator** (a persistent ReAct agent — the "project manager") dispatches work to the right agent, reading coverage state, deciding which scope is most valuable to push next, and routing to either a fresh agent (spawn) or an existing one (resume).
4. After each round, a deterministic **`update_state`** node merges per-dispatch coverage deltas into a master coverage DB and patches the testplan.
5. Loops until the goal is met, the budget is spent, or progress plateaus.

Mental model: **manager + engineers**. The orchestrator is the manager; agents are persistent engineers each owning a feature codebase. They are not one-shot tools.

## Design docs — read these first

Authoritative reference. New code must match these contracts.

- [.claude/plans/state.md](.claude/plans/state.md) — LangGraph state schemas (`OrchestratorState`, `AgentState`, `AgentMetadata`)
- [.claude/plans/graph.md](.claude/plans/graph.md) — node topology, spawn/resume routing, agent subgraph
- [.claude/plans/tools.md](.claude/plans/tools.md) — tool taxonomy and per-node registration
- [.claude/plans/testplanning.md](.claude/plans/testplanning.md) — testplan schema and dispatch contract
- [.claude/plans/coverage.md](.claude/plans/coverage.md) — three-layer coverage model, simulator-native merge
- [.claude/plans/work-dir.md](.claude/plans/work-dir.md) — on-disk layout and sandbox enforcement
- [.claude/plans/prompts.md](.claude/plans/prompts.md) — layered prompt structure, per-node templates
- [.claude/plans/context.md](.claude/plans/context.md) — three persistent conversations, transient-read policy
- [.claude/plans/logging.md](.claude/plans/logging.md) — events.jsonl, run.log, agent lifecycle events
- [.claude/plans/legacy.md](.claude/plans/legacy.md) — what to reuse from `legacy_src/`, what to drop
- [environment.md](environment.md) — directory layout, dependencies, module organization

When a design doc and your intuition disagree, the doc wins. If you find a real conflict between docs, surface it — do not paper over it.

## Legacy code — your second-best resource

[legacy_src/](legacy_src/) is a previous working implementation of a single-agent ReAct version of this idea. **Do not run it; do not copy whole files blindly.** But its modules are excellent references:

- [legacy_src/simulators/](legacy_src/simulators/) — `SimulatorAdapter` for Questa and Verilator. Port wholesale; the new framework's `run_sim` tool wraps these.
- [legacy_src/utils/dashboard_loader.py](legacy_src/utils/dashboard_loader.py) — `dashboard.json` → `DesignConfig` resolution with `$(BASE_DIR)` substitution. Reuse.
- [legacy_src/utils/event_log.py](legacy_src/utils/event_log.py) — JSONL event logger; the shape generalizes cleanly to the new event schema.
- [legacy_src/utils/conversation_logger.py](legacy_src/utils/conversation_logger.py) — per-conversation transcripts. Adapt for three persistent conversations.
- [legacy_src/tools/filesystem.py](legacy_src/tools/filesystem.py) — bounded `read_file` / `write_file` with sandbox path resolution. Extend with `edit_file`.
- [legacy_src/tools/coverage.py](legacy_src/tools/coverage.py) — coverage parsing/merging logic.

What to **avoid** importing from legacy: `tools/analysis.py` (context-bloat), the legacy ReAct graph (`graphs/react.py`), and the env-var-driven `config.py` (replaced by frozen `RunConfig` snapshot at run start).

[.claude/plans/legacy.md](.claude/plans/legacy.md) is the full reuse map. Consult it.

## Engineering practices

**LangGraph**

- Use the LangGraph MCP server when uncertain about API: `mcp__docs-langchain__search_docs_by_lang_chain`. Prefer it over guessing.
- Prefer **typed `TypedDict` state** with explicit `Annotated[..., reducer]` fields. Don't put mutable state outside the graph.
- One writer per state field. The topology enforces this — don't bypass it with module-level globals.
- Subgraphs (the persistent agent) get their own checkpointer keyed by `agent_id`.
- `Send` is the only fan-out primitive; do not spawn agents via threads or asyncio directly.

**Python**

- Python 3.11+. Use modern syntax (`list[str]`, `X | None`, `match`).
- Type hints on every public function. `mypy --strict` should be clean for new modules.
- Pydantic v2 for any cross-boundary structured data (testplan, dispatch brief, return). `TypedDict` for in-graph state where reducers are needed.
- Pure functions where possible. Side effects (filesystem, simulator) live behind named tools and adapters.
- Use `pathlib.Path`, never raw strings, for paths.
- No bare `except:`. Catch the narrow exception or let it propagate.
- Logging via the project's event/run-log subsystem (see [logging.md](.claude/plans/logging.md)) — not `print` and not `logging.getLogger()` ad hoc.

**Code organization**

- New code goes under `src/covagent/` (see [environment.md](environment.md)). Do not modify `legacy_src/` — treat it as read-only reference.
- One concept per module. If a file grows past ~400 lines, ask whether it's doing two things.
- Tools are registered through a thin wrapper that emits `tool.called` / `tool.returned` events automatically. Do not call LLM-facing tools without the wrapper.
- Sandbox enforcement (`work_dir` containment) lives in path-resolution helpers, not scattered through tool bodies.

**Tests**

- Pytest. Unit tests for pure logic (testplan patching, coverage merge math, path resolution). Integration tests for graph nodes use mock simulators (port `legacy_src/tools/simulation_mock.py`).
- Do not write tests that exercise a live LLM in CI. Mock the model surface.

**Process**

- Match the design doc's contract exactly. If the doc says `OrchestratorAction` is a tagged union with `kind: Literal["dispatch", "terminate"]`, implement that — don't add a third variant.
- When the design is genuinely silent on a small detail, make the obvious local choice and move on. When it's silent on something architectural, stop and ask.
- Small, focused commits. The git history should let a reviewer follow the design → code mapping.
- No dead code, no commented-out blocks, no TODOs without an owner.

## What "done" looks like for an implementation task

- Code matches the relevant design doc's contract (state shape, tool signature, node responsibility).
- Type-checks clean.
- Unit tests cover the non-trivial logic.
- New tools are registered through the event-emitting wrapper.
- New filesystem writes resolve through the sandbox helper.
- The change is a step toward the manager-and-engineers architecture, not a regression toward one-shot generation.

If you finish a task and any of the above is missing, the task isn't done.
