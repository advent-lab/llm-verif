# State — design reference

LangGraph state schema for the orc-gen workflow. State is the spine: every node, tool, prompt, and log entry references it. This doc fixes the shape and reducers; the graph design (next) and tool set (later) build on top.

## Two state scopes

**Orchestrator state** is the top-level graph state — long-lived across iterations, persisted via checkpointing. **Generator (agent) state** is per-agent and persistent across the run: each agent is a checkpointed subgraph keyed by `agent_id`. State persists between dispatches; the conversation grows across invocations.

This split mirrors single-writer ownership from testplanning.md: orchestrator state is canonical (testplan, dispatch log, agent registry, run config); agent state is the agent's private working memory. Parallel agents never touch each other's state and never write to the orchestrator state directly — they return structured results that the orchestrator reconciles.

## Orchestrator state

```python
class OrchestratorState(TypedDict):
    # Static — set once at run start
    config: RunConfig

    # Set once at end of INIT — concise summary of the design produced by init.
    # Becomes part of orchestrate's persistent context. Heavy raw spec/RTL
    # excerpts read during init are NOT carried here; only the digest is.
    design_digest: str | None

    # Canonical artifacts — orchestrator-only writers
    testplan: Testplan                          # see testplanning.md
    dispatch_log: list[DispatchRecord]          # append-only audit trail
    agents: dict[str, AgentMetadata]            # agent registry, keyed by agent_id

    # Loop control
    iteration: int
    run_status: Literal["init", "running", "blocked", "done", "errored"]

    # Persistent orchestrator conversation — grows across the entire LOOP phase.
    # Created at first orchestrate entry (post-init), never reset. See context.md.
    # Note: init runs in its own short-lived conversation that is NOT stored
    # here; it hands off via `testplan` and `design_digest`.
    messages: Annotated[list[AnyMessage], add_messages]

    # Per-iteration scratchpad — cleared at iteration boundary
    cycle: CycleScratch
```

### `RunConfig` (static)

```python
class RunConfig(TypedDict):
    mode: Literal["functional", "code"]
    workspace: str                              # root path for all artifacts
    rtl: list[str]                              # RTL source paths
    spec: str | None                            # spec doc path (functional only)
    cov_db: str                                 # coverage DB path
    sim: SimulatorConfig                        # tool, flags, seed strategy
    coverage_target: dict                       # mode-specific (see testplanning.md)
    budgets: GlobalBudgets                      # max iterations, max parallel, etc.
```

Lives in state (not module constants) so the graph is testable with synthetic configs and replayable from a checkpoint without external setup.

`RunConfig` is populated at run startup from one of two sources: a **dashboard.json entry** (preferred — design name resolved to spec/RTL/context paths, supports running against the [data/](../../data/) benchmark designs without per-design reconfiguration), or **direct paths** for ad-hoc runs. Both produce the same `RunConfig`; the loader is a startup concern, not a runtime one. See [legacy.md](legacy.md) for the dashboard.json schema and integration notes.

### `DispatchRecord` (append-only)

```python
class DispatchRecord(TypedDict):
    dispatch_id: str
    iteration: int                              # which orchestrator iteration
    feature: str                                # grouping label from brief
    item_names: list[str]                       # items targeted
    brief_summary: str                          # condensed, for LLM recall
    return_summary: str                         # condensed, post-reconciliation
    work_dirs: list[str]                        # per-generator work dirs
    timestamp: str
```

Separate from per-item `history` for a reason: `history` captures *what happened to an item*; `dispatch_log` captures *what the orchestrator decided*. The orchestrator scans the log for "what have I tried recently"; per-item history feeds future briefs for that item. Different read patterns, different surfaces.

### `AgentMetadata` (registry entry)

```python
class AgentMetadata(TypedDict):
    agent_id: str                               # e.g., "agent_csr_a3f1"
    feature_label: str                          # human-readable scope name
    scope_items: list[str]                      # immutable item names this agent owns
    work_dir: str                               # filesystem path, persistent
    status: Literal["active", "idle", "retired"]  # lifecycle state
    spawned_at: str                             # ISO timestamp
    last_invoked_at: str | None                 # ISO timestamp; null if never invoked
    invocation_count: int                       # how many dispatches it has handled
```

The orchestrator uses `agents` to:
- Decide whether to spawn a new agent or resume an existing one for a given dispatch.
- Track which agents are idle (signed off, items complete) vs. active (work outstanding) vs. retired (explicitly stood down by orchestrator judgment).

`scope_items` is **immutable after spawn**. New testplan items either fit an existing agent's scope (orchestrator extends `scope_items` only at spawn time, never after) or warrant a new agent. This avoids agents fighting over items.

### `CycleScratch` (transient)

```python
class CycleScratch(TypedDict):
    candidate_features: list[FeaturePlan]       # this iteration's grouping decision
    in_flight: list[GeneratorHandle]            # generators currently dispatched
    pending_results: list[GeneratorReturn]      # collected before reconciliation
    coverage_snapshot: CoverageSnapshot | None  # taken at iteration start
```

Cleared at iteration boundary by an explicit reducer hook. Keeps long-running state lean and prevents stale planning data from leaking across iterations.

## Agent state

Each agent is a checkpointed subgraph keyed by `agent_id`. State persists across dispatches: the conversation grows, the work_dir accumulates files, coverage_history extends. State is loaded from checkpoint when a dispatch resumes the agent and saved when the agent pauses (after `finish`).

```python
class AgentState(TypedDict):
    # Identity — set at spawn, immutable
    agent_id: str
    feature_label: str
    scope_items: list[str]                      # the items this agent owns
    work_dir: str                               # persistent across the whole run

    # Per-invocation inputs — refreshed each dispatch
    current_brief: DispatchBrief | None         # the brief for the active invocation; null when idle

    # Loop control (per-invocation, reset each dispatch)
    attempt: int                                # 1..budget.max_iterations within current invocation
    stop_reason: StopReason | None              # filled when current invocation's loop exits

    # LLM scaffolding — PERSISTENT across dispatches
    # The conversation grows each invocation; system prompt loaded once at spawn.
    messages: Annotated[list[AnyMessage], add_messages]

    # Coverage tracking — accumulates across dispatches
    coverage_baseline: CoverageSnapshot         # baseline at most recent invocation start
    coverage_history: Annotated[list[CoverageSnapshot], operator.add]   # all snapshots, all invocations

    # Output staging — built up over current invocation, returned at finish
    proposed_status: dict[str, Literal["complete", "incomplete", "blocked"]]
    report: GeneratorReport
```

Two important consequences of persistence:

- **`messages` is the agent's working memory across the whole run.** When the orchestrator resumes the agent, it sees its own prior reasoning, prior tool calls, prior sim outputs (subject to the transient-read policy from context.md). This is the core value of persistent agents.
- **`current_brief` rotates each invocation.** When the orchestrator resumes, the new brief is appended as a user turn into the persistent conversation; the field gives the per-invocation nodes (plan, act, check) a typed handle without re-parsing the message history.

`coverage_history` accumulates across all invocations — plateau detection looks at the tail relative to the *current* invocation's baseline.

## Reducers

Reducers are explicit so concurrent writes — especially Send fan-out — are well-defined.

| Field | Reducer | Why |
|---|---|---|
| `testplan` | replace | `orchestrate` and `update_state` are the only writers; they never run concurrently |
| `dispatch_log` | append | Audit trail must be ordered, never overwritten |
| `messages` | `add_messages` | LangGraph standard; merges by message ID. **Never reset** during LOOP — this is the persistent orchestrator conversation. See context.md. |
| `design_digest` | replace | Set once by init; constant thereafter |
| `agents` | dict-merge | `orchestrate` writes new entries on spawn; `update_state` writes lifecycle status changes |
| `cycle` | replace, with `reset_at_iteration` hook | Transient; explicit lifecycle |
| `messages` (agent) | `add_messages` | Persistent across the run; never reset |
| `coverage_history` (agent) | `operator.add` | Sequential appends across dispatches |
| `proposed_status` (agent) | dict-merge | Built up per item across attempts within current invocation |

**No reducer guards the testplan itself.** Testplan mutations go through tool calls (`patch_testplan`, `append_history`) executed by either `orchestrate` (judgment-driven changes: blocking, waivers, instruction additions) or `update_state` (routine post-dispatch merge). These two nodes never run concurrently — the graph topology serializes them — so the single-writer invariant is upheld without a reducer.

## What lives outside state

State is for what the graph reasons about. Other persistence layers handle the rest:

- **Test code, sim artifacts, waveforms** → generator `work_dir/` on disk. Referenced from state by path, never inlined.
- **Coverage DB** → simulator-managed file (UCDB / `.cov` / `.vdb`). Queried via `query_coverage`; never copied into state.
- **Logs** → separate logging subsystem (see logging.md). State carries pointers (e.g., `dispatch_id`), not log lines.
- **Spec docs, RTL** → filesystem; state holds paths.

Keeping bulk artifacts out of state keeps checkpoints small, keeps LLM context clean, and decouples persistence concerns from control flow.

## State lifecycle (one orchestrator iteration)

1. **`orchestrate` entry** — persistent conversation resumes; `cycle` reset for the new iteration if a `DispatchPlan` is about to be emitted.
2. **`orchestrate` LLM turn** — reasons over running history + `design_digest` + most recent `update_state` summary + `agents` registry; emits an `OrchestratorAction` (dispatch or terminate). Each dispatch in the plan carries an `agent_id`: new ID → spawn; existing ID → resume.
3. **`dispatch`** — Send fans out. For new agents, creates `AgentState` and `AgentMetadata` entry. For existing agents, loads `AgentState` from checkpoint and appends the new brief as a user turn.
4. **Collect** — agent returns flow into `cycle.pending_results` via a list-append reducer on the join node. Each agent's state is checkpointed (paused) at finish.
5. **`update_state`** — calls `query_coverage`, compares with proposals, applies routine `patch_testplan` / `append_history`, updates `AgentMetadata.status` (idle when all scope_items complete), appends a `DispatchRecord`, posts a structured summary turn into `messages`. `iteration` increments here too.
6. **Loop back to `orchestrate`** — the LLM sees the summary turn and decides next step (continue with new `DispatchPlan`, or terminate via `RouteDecision`).

Each step maps to one or two graph nodes; the concrete node decomposition belongs in graph.md.

## What this design buys us

- **Single-writer testplan** enforced by topology + tools, not reducers — simpler invariant.
- **Persistent orchestrator messages** preserve LLM reasoning across iterations; combined with `design_digest`, they give the orchestrator a coherent agent identity throughout the run.
- **Persistent agent state** lets each generator accumulate domain expertise within its scope. The CSR agent learns the CSR module across iterations rather than being reborn each dispatch.
- **Agent registry as orchestrator's roster** — `agents` is the manager's view of "who works on what, who's busy, who's signed off."
- **Immutable `scope_items`** prevents agents from competing for items and makes the manager/engineer mental model literally enforced in state.
- **Transient `cycle` scratchpad** keeps long-lived state lean and prevents iteration-to-iteration leakage on bookkeeping fields.
- **External artifacts referenced by path** keeps state small and LLM context focused.
- **Dispatch log + per-item history split** gives the orchestrator two complementary recall surfaces without duplication.
