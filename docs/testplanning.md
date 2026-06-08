# Testplanning — design reference

Reference for the testplan structure, dispatch contracts, coverage tracking, and management tools used by the orc-gen workflow. Captures decisions and the reasoning behind them so future design work (graph, state, prompts, tools, logging) stays consistent.

## Modes

A run targets **either** functional **or** code coverage, never both. Mode is a config field that flows through the whole workflow. The orchestrator loop, brief schema, and tool surface are mode-agnostic in shape — only the testplan content and the source of items differ.

- `mode: "functional"` — items come from spec + cov model
- `mode: "code"` — items come from RTL hierarchy

Mixed runs are achieved by chaining two single-mode runs against the same workspace, not by a hybrid loop. Different metrics drive different generation strategies, and asking one generator dispatch to optimize both dilutes the goal.

## Testplan structure

Single global testplan, **owned solely by the orchestrator**. Test generators never write to it. Surgical patches via tool calls. This avoids merge/lock complexity at the cost of one extra hop on the return path — worth it.

### Schema by mode

```
mode = "functional":
  testpoints[]      # spec-mandated stimulus items
  covergroups[]     # spec-mandated closure goals

mode = "code":
  code_scopes[]     # RTL scopes (modules / files / hierarchical paths)
```

Asymmetry is intentional: functional spec mandates two independent deliverable lists (stimulus + closure) with a many-to-many relationship. Code spec mandates one (cover the RTL); stimulus is scaffolding the orchestrator invents on demand. Mirroring the functional schema in code mode would duplicate state and let it drift.

### Per-item fields (same shape across all lists)

```jsonc
{
  "name": "...",
  "description": "...",
  "steps": ["..."],                   // optional how-to hints
  "status": "todo|incomplete|complete|blocked",
  "history": [                        // append-only, structured
    {
      "timestamp": "...",
      "agent_id": "...",
      "outcome": "passed|failed|partial|errored",
      "summary": "...",
      "artifacts_path": "..."         // pointer to test code in agent work dir
    }
  ],
  "owner_agent_id": "agent_csr_a3f1" | null,  // assigned at first dispatch, immutable thereafter
  "waiver": null | { "reason": "...", "approver": "...", "date": "..." },
  "coverage": {                       // present on covergroups / code_scopes
    "pct": 72.5,
    "items_hit": 145,
    "items_total": 200,
    "unhit_items": ["..."],           // truncate if huge
    "snapshot_at": "...",
    "target_pct": 95
  }
}
```

Notes on key fields:

- **`status` includes `blocked`** — distinguishes "orchestrator gave up, needs human or waiver" from "still trying" (`incomplete`) and from positive sign-off (`waiver`). Without it, exhausted items get re-dispatched forever.
- **`history` is structured, not free-form snippets.** The orchestrator must summarize history into future dispatch briefs; free-form blobs make that unreliable. Keep entries terse and semantic.
- **`owner_agent_id` binds an item to a persistent generator agent.** Set at first dispatch and immutable — items do not migrate between agents. Test code lives in the owning agent's work dir (see work-dir.md), not in the testplan. The orchestrator uses this field to decide whether to resume an existing agent or spawn a new one for a given item. This is also why code mode needs no separate `testpoints[]`.
- **`coverage` block is a cache** of last-observed values — authority lives in the coverage DB. Carried so the orchestrator can reason about progress without re-querying.
- **Status is the orchestrator's responsibility.** Generators *propose* status; orchestrator decides after reconciliation against `query_coverage`.

## Management tools

Tool surface is small and domain-shaped, not generic. LLMs construct domain calls more reliably than RFC-6902-style patches.

- **`read_testplan(target?, filter?)`** — surgical read by item name, or filtered list (`{status: "todo"}`, `{feature: "csr"}`), or full plan. Filter form is the orchestrator's main scheduling primitive.
- **`read_summary()`** — counts and percentages only. For "are we done" checks without paying the full plan token cost.
- **`patch_testplan(target_type, name, fields)`** — merge fields into a single existing item. Strict schema validation; fail loud on hallucinated fields.
- **`append_history(target_type, name, entry)`** — dedicated affordance because history is append-only. Separating it from `patch_testplan` documents intent and avoids accidental overwrites.
- **`dispatch_test_gen(brief)`** — orchestrator → generator hand-off. See dispatch brief below.
- **`query_coverage(scope, mode)`** — uniform interface for both code and functional. Returns structured numbers, never LLM-parsed report text. Used by both orchestrator and generators.

## Dispatch brief (orchestrator → generator)

In-memory only, never persisted as a separate document. Feature grouping is purely an orchestrator-side organizing concept; items can belong to multiple features so feature is **not** a testplan field.

```jsonc
{
  "feature": "csr",                       // grouping label, not authoritative
  "testpoints":  [ ...filtered subset... ],
  "covergroups": [ ...just the relevant ones, with current coverage... ],
  "code_scopes": [ ...code mode equivalent... ],
  "instructions": "...",                  // orchestrator's directed guidance
  "rtl_context": ["..."],                 // pre-resolved paths
  "spec_excerpts": ["..."],               // pre-extracted, not full doc
  "baseline_coverage": { ... },           // snapshot before this dispatch
  "goal": {                               // explicit definition-of-done
    "type": "absolute" | "delta" | "bin_set" | "stimulus_only",
    "target": ...
  },
  "budget": { "max_iterations": 5, "max_tokens": ... }
}
```

Why explicit goal + budget: LLMs reliably under- or over-shoot when the success criterion is implicit, and they loop forever without a budget.

Each item in the brief carries its own `history` and orchestrator-written `instructions` — this is where the orchestrator's reasoning value-add lives ("previous attempt only used auto mode; try `manual_operation == 1`").

## Return contract (generator → orchestrator)

Generator returns a tool-call result, never writes the testplan directly.

```jsonc
{
  "feature": "csr",
  "testpoints":  [ { "name": "...", "history": [...], "coverage": {...},
                     "proposed_status": "complete|incomplete|blocked",
                     "work_dir": "..." } ],
  "covergroups": [ ... ],
  "code_scopes": [ ... ],
  "report": {
    "issues_encountered": [...],
    "blockers": [...],
    "recommendations_for_next_pass": [...]
  }
}
```

`proposed_status` is a recommendation, not authority. Orchestrator reconciles against `query_coverage` before patching. Lightly-structured `report` (vs. free-form) keeps shape consistent across runs.

## Coverage tracking

Three things kept distinct:

1. **Ground truth** — coverage DB written by the simulator (UCDB / `.cov` / `.vdb`). Authority.
2. **Testplan cache** — last-observed `coverage` blocks on items. May be stale until refreshed.
3. **Per-task delta** — generator computes its own progress as `current - baseline_coverage` from the brief.

Critical rule: **never have an LLM extract coverage numbers from raw report text.** Always `query_coverage`. Hallucinated digits are the single biggest source of "I closed it" lies.

### Per-task goal types (set in dispatch brief)

- **Absolute** — "raise covergroup X to ≥ 95%"
- **Delta** — "improve X by ≥ 20pp from baseline"
- **Bin-set** — "hit these specific unhit bins: [list]"
- **Stimulus-only** — "produce a passing test for this testpoint" (no coverage gate)

### Generator stop conditions (priority order, hard-coded into the loop)

1. **Budget exhausted** → return what you have, propose `incomplete`, reason `budget`.
2. **Goal reached** → propose `complete`.
3. **Plateau** — N consecutive iterations with < ε improvement → propose `blocked`. (Start ε≈1pp, N≈3.)
4. **Hard error** — sim/compile fails K times unrecovered → propose `blocked` with last failure attached.

Without explicit plateau detection LLMs grind on diminishing returns indefinitely.

## Reconciliation (orchestrator post-dispatch)

After each generator return:

1. Run `query_coverage` for items the generator touched, plus global if needed.
2. Compare to generator's `proposed_status` and reported `coverage`.
3. Patch testplan:
   - Claim agrees with truth → flip `status` as proposed.
   - Claim disagrees (over-reported) → keep `incomplete`, append history note. This is the hallucination guard.
   - `proposed: blocked` → orchestrator decides between re-dispatch with new `instructions`, escalate to waiver, or accept `blocked`.
4. Append `agents[]` with the generator's `work_dir`.

## Targets and config

```
coverage_target:
  functional: 100
  code: { line: 95, toggle: 90, branch: 95, fsm: ... }
```

Per-item overrides allowed for known-unreachable bins, but those should usually become waivers rather than soft targets.

## What this design buys us

- **Single writer** keeps consistency simple; no merge protocol.
- **Single workflow shape across modes** keeps tool surface small.
- **Structured history + goal + budget** keeps LLM behavior bounded and forward-progressing.
- **Reconciliation against ground truth** prevents agents from declaring victory they didn't earn.
- **In-memory feature briefs** keep generator context small and focused without document drift.
