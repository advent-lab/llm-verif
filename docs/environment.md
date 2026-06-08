# Environment — project setup reference

Project layout, dependencies, and module organization for the new CovAgent codebase. This doc is the source of truth for "where does this file live and what does it import."

## Repository layout

```
llm-verif/                              # repo root
├── AGENTS.md                           # implementation guide for coding agents
├── README.md                           # user-facing overview (TBD)
├── pyproject.toml                      # build config, deps, tool config
├── uv.lock                             # locked dependency graph (uv-managed)
├── dashboard.json                      # design registry — name → RTL/spec paths
├── .claude/plans/                      # design docs (authoritative)
│   ├── environment.md                  # this file
│   ├── state.md, graph.md, tools.md, ...
├── src/covagent/                       # new framework code (sole production source)
│   ├── __init__.py
│   ├── config.py                       # RunConfig dataclass (frozen, snapshotted per run)
│   ├── cli.py                          # `covagent` entry point
│   ├── state/
│   │   ├── __init__.py
│   │   ├── orchestrator.py             # OrchestratorState, AgentMetadata
│   │   ├── agent.py                    # AgentState
│   │   ├── testplan.py                 # Testpoint, Covergroup, Coverpoint, Bin (Pydantic)
│   │   └── dispatch.py                 # DispatchBrief, GeneratorReport, OrchestratorAction
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── orchestrator.py             # top-level graph: init → loop → finalize
│   │   ├── nodes/
│   │   │   ├── init.py                 # init subgraph
│   │   │   ├── orchestrate.py          # persistent orchestrator turn
│   │   │   ├── dispatch.py             # spawn vs resume routing, Send fan-out
│   │   │   ├── update_state.py         # deterministic merge node
│   │   │   └── finalize.py             # final summary, snapshots
│   │   └── agent_subgraph.py           # persistent agent (plan → act → finish/PAUSE)
│   ├── tools/
│   │   ├── __init__.py                 # tool registration + event-emitting wrapper
│   │   ├── filesystem.py               # read_file, write_file, edit_file (sandboxed)
│   │   ├── rtl_spec.py                 # read_rtl, read_spec_excerpt (transient)
│   │   ├── coverage.py                 # query_coverage, take_snapshot
│   │   ├── simulation.py               # run_sim
│   │   ├── testplan.py                 # patch_testplan, append_history, read_testplan
│   │   └── agents.py                   # read_agents (orchestrator roster view)
│   ├── simulators/                     # ported from legacy_src/simulators/
│   │   ├── __init__.py
│   │   ├── base.py                     # SimulatorAdapter ABC
│   │   ├── questa.py
│   │   └── verilator.py
│   ├── prompts/
│   │   ├── __init__.py                 # Jinja loader
│   │   ├── shared/                     # blocks reused across nodes
│   │   ├── init.j2
│   │   ├── orchestrate.j2
│   │   ├── agent_plan.j2
│   │   └── agent_act.j2
│   ├── logging/
│   │   ├── __init__.py
│   │   ├── events.py                   # events.jsonl writer
│   │   ├── run_log.py                  # human-readable formatter
│   │   └── conversations.py            # per-conversation transcript writer
│   ├── workspace/
│   │   ├── __init__.py
│   │   ├── layout.py                   # path helpers for run/agent/dispatch dirs
│   │   ├── sandbox.py                  # resolve_write_path enforcement
│   │   └── dashboard.py                # dashboard.json loader (from legacy_src/utils/dashboard_loader.py)
│   └── coverage/
│       ├── __init__.py
│       ├── merge.py                    # simulator-native merge wrapper
│       └── snapshot.py                 # snapshot policy
├── tests/
│   ├── unit/                           # pure-logic tests
│   ├── integration/                    # graph nodes with mock simulators
│   └── fixtures/                       # tiny RTL/spec fixtures, sample testplans
├── data/                               # design corpus (RTL, specs) — read-only inputs
│   └── _functional_coverage_code/      # functional-coverage example testbenches
├── examples/
│   └── testplan.json                   # example testplan for reference
├── legacy_src/                         # previous implementation (reference only, do not modify)
└── workspaces/                         # default RunConfig.workspace root (created at runtime)
    └── default/
        ├── shared/                     # symlinks to data/<design>/rtl, /spec
        └── runs/                       # per-run dirs (see work-dir.md)
```

The new framework lives entirely under `src/covagent/`. `legacy_src/` is preserved as a reference and is never imported by new code.

## pyproject.toml

```toml
[project]
name = "covagent"
version = "0.1.0"
description = "Coverage-driven hardware verification orchestrator"
requires-python = ">=3.11"
dependencies = [
    "langgraph>=0.2",
    "langchain-core>=0.3",
    "langchain-anthropic>=0.2",
    "pydantic>=2.7",
    "jinja2>=3.1",
    "rich>=13",
    "click>=8.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "mypy>=1.10",
    "ruff>=0.5",
]

[project.scripts]
covagent = "covagent.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = true
packages = ["covagent"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Dependency rationale (top-level only):

- **langgraph** — graph topology, Send fan-out, checkpointers for persistent agents.
- **langchain-core / langchain-anthropic** — message types and Anthropic chat model. We call Claude via `ChatAnthropic`; the model name is read from `RunConfig`.
- **pydantic v2** — testplan and dispatch boundary objects (validation, JSON round-trip).
- **jinja2** — prompt templates with shared blocks.
- **rich** — pretty-printing for live `run.log` rendering and CLI output.
- **click** — `covagent` CLI surface.

No Anthropic SDK direct dependency — `langchain-anthropic` provides the model wrapper. No async HTTP client beyond what LangChain pulls in transitively.

## Module organization principles

- **One concept per module.** `state/agent.py` defines `AgentState` and nothing else. `tools/filesystem.py` owns `read_file` / `write_file` / `edit_file`. Splitting along these lines keeps imports shallow and tests focused.
- **No circular imports.** `state/` is a leaf. `tools/` imports from `state/` and `workspace/` but not from `graph/`. `graph/` is the top of the dependency tree.
- **Tools are registered, not imported by name from nodes.** Each node receives its tool set from `tools/__init__.py`'s registration table — see [.claude/plans/tools.md](tools.md) for the per-node mapping.
- **Filesystem writes route through `workspace/sandbox.py`.** Tools never call `Path.write_text` directly; they go through `resolve_write_path(state, raw_path)` which enforces the per-agent sandbox.
- **Events emit through a wrapper.** `tools/__init__.py` exposes a decorator that wraps every LLM-facing tool with `tool.called` / `tool.returned` event emission. New tools opt in by being registered here, not by manual emit calls.
- **Prompts are data, not code.** Jinja templates in `prompts/` are loaded by ID; per-node Python code does not contain prompt strings inline.

## Setup

```bash
# clone, then:
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

Runtime configuration is a single `RunConfig` object (instantiated by the CLI from flags or a config file), snapshotted to `<run>/config.json` at run start. There are no environment-variable knobs in the new framework — that pattern from legacy is intentionally dropped.

## Workspaces

`RunConfig.workspace` defaults to `./workspaces/default/`. The CLI creates it if missing and ensures `shared/rtl/` and `shared/spec/` are populated (typically as symlinks to `data/<design_name>/rtl/` and `data/<design_name>/spec/`, resolved via `dashboard.json`). All run artifacts land under `<workspace>/runs/run_<timestamp>_<hash>/` — see [.claude/plans/work-dir.md](work-dir.md).

## What lives where — quick reference

| Need | Look in |
|------|---------|
| State schema for the orchestrator | `src/covagent/state/orchestrator.py` |
| State schema for an agent | `src/covagent/state/agent.py` |
| Top-level graph wiring | `src/covagent/graph/orchestrator.py` |
| Persistent agent subgraph | `src/covagent/graph/agent_subgraph.py` |
| Spawn vs resume routing | `src/covagent/graph/nodes/dispatch.py` |
| Coverage merge | `src/covagent/coverage/merge.py` (wraps `simulators/<sim>.py`) |
| Sandbox path resolution | `src/covagent/workspace/sandbox.py` |
| Tool wrapper / event emit | `src/covagent/tools/__init__.py` |
| Prompt templates | `src/covagent/prompts/*.j2` |
| CLI entry | `src/covagent/cli.py` |
| Reference for sim adapters | `legacy_src/simulators/` |
| Reference for dashboard loader | `legacy_src/utils/dashboard_loader.py` |
