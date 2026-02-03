# AGENTS.md - Coding Agent Alignment

## 1) Project Scope (Overview)
Spec2Cov builds agentic workflows (LangGraph) for automated hardware verification.
Given a design spec + RTL, the system iterates on generated testbenches, simulation runs,
and coverage analysis to drive toward coverage closure.

Tech stack (core):
- Python (project code and CLI entrypoints)
- LangGraph + LangChain tools (graph orchestration + tool calling)
- Typed state / structured outputs (TypedDict/Pydantic as appropriate)
- Simulator + coverage tooling (e.g., QuestaSim) behind tools interfaces

## 2) Project Structure (Root)
- src/   : main Python package (graphs, tools, prompts, utilities)
- docs/  : project documentation (architecture, tool docs, tasks, plans, notes)
- data/  : design corpus (each design typically contains rtl/ and docs/)

## 3) Instructions (Follow for Every Prompt)

### A) Always Ground Yourself First
- Read the most relevant docs in docs/ before coding (ARCH, tool docs, task specs).
- Inspect existing code before adding abstractions; match local conventions.
- Prefer searching for existing patterns/usages over inventing new APIs.

### B) LangGraph: Use the MCP Docs (Do Not Guess)
- Use the LangGraph MCP server to look up the correct APIs, patterns, and best practices.
- If an API detail is uncertain, check MCP docs first, then implement.
- Prefer stable, documented LangGraph patterns; avoid deprecated usage.

### C) Ask Follow-up Questions Aggressively
Ask clarifying questions whenever requirements are ambiguous, especially around:
- Target workflow behavior, termination criteria, and success metrics
- Expected inputs/outputs and file locations
- Simulator availability, command expectations, timeouts, and platform constraints
- Whether the change is experimental vs production-bound

### D) Code Quality and Maintainability
- Keep changes small, focused, and easy to review.
- Write clean, readable Python: explicit names, simple control flow, minimal coupling.
- Handle errors explicitly and return actionable diagnostics (stdout/stderr, return codes).
- Keep large artifacts on disk (logs, reports, RTL, testbenches); store only paths/metadata
  in agent state.

### E) Documentation is Part of the Feature
- Update docs/ARCH.md when architecture or state/tool contracts change.
- Add/extend docs/tool documentation when tool behavior or outputs change.
- Keep documentation concise and task-oriented.

### F) Track Debt, Workarounds, and Risks
- Record temporary hacks, hardcoded assumptions, and known issues in docs/NOTES.md.
- Record future work items in docs/TODO.md.
- Record risky decisions, environment pitfalls, or gotchas in docs/WARNINGS.md.

### G) Validation
- Prefer running the smallest relevant check first (unit tests / targeted script).
- Do not fix unrelated issues while validating; note them separately if discovered.

### H) Operational Safety
- Avoid destructive commands or sweeping refactors without explicit confirmation.
- Keep secrets out of logs/docs; rely on .env and documented configuration patterns.
