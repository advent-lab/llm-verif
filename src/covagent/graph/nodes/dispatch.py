"""DISPATCH node — spawn vs resume routing, Send fan-out to agent subgraphs."""

from __future__ import annotations

from typing import Any

from langgraph.types import Send

from covagent.graph.deps import RuntimeDeps
from covagent.logging.events import iso_now
from covagent.state.agent import AgentState
from covagent.state.dispatch import DispatchBrief
from covagent.workspace.layout import (
    AgentPaths,
    DispatchPaths,
    bootstrap_agent,
    bootstrap_dispatch,
    make_dispatch_id,
)


def make_dispatch_node(deps: RuntimeDeps):
    def dispatch_node(state: dict) -> Any:
        cycle = state.get("cycle") or {}
        action = cycle.get("pending_action") or {}
        plan = (action.get("dispatch_plan") or {}).get("briefs") or []
        if not plan:
            # Empty plan — surface as error and return to finalize.
            deps.tee.emit(
                "warning.raised",
                {"where": "dispatch", "message": "empty dispatch plan"},
                iteration=state.get("iteration"),
                node="dispatch",
            )
            return {"cycle": cycle}

        # Concurrency check — no agent_id twice.
        seen: set[str] = set()
        for b in plan:
            if b.agent_id in seen:
                deps.tee.emit(
                    "error.raised",
                    {
                        "where": "dispatch",
                        "message": f"agent_id {b.agent_id} appears twice in plan",
                    },
                    iteration=state.get("iteration"),
                    node="dispatch",
                )
                return {"cycle": cycle, "run_status": "errored"}
            seen.add(b.agent_id)

        iteration = state.get("iteration", 0) + 1
        agents: dict = dict(state.get("agents") or {})
        new_dispatches: list[Send] = []

        for seq, brief in enumerate(plan, start=1):
            dispatch_id = make_dispatch_id(iteration, seq)
            existing = agents.get(brief.agent_id)
            agent_paths = AgentPaths.for_agent(deps.run_paths, brief.agent_id)
            dispatch_paths = DispatchPaths.for_dispatch(agent_paths, dispatch_id)

            if existing is None:
                bootstrap_agent(agent_paths)
                agents[brief.agent_id] = {
                    "agent_id": brief.agent_id,
                    "feature_label": brief.feature_label,
                    "scope_items": list(brief.scope_items),
                    "work_dir": str(agent_paths.work_dir),
                    "status": "active",
                    "spawned_at": iso_now(),
                    "last_invoked_at": iso_now(),
                    "invocation_count": 1,
                }
                deps.tee.emit(
                    "agent.spawned",
                    {
                        "agent_id": brief.agent_id,
                        "feature_label": brief.feature_label,
                        "scope_items": list(brief.scope_items),
                        "work_dir": str(agent_paths.work_dir),
                        "spawned_at_iteration": iteration,
                    },
                    iteration=iteration,
                    node="dispatch",
                    agent_id=brief.agent_id,
                )
            else:
                # Resume — feature_label/scope_items must match.
                if (
                    existing.get("feature_label") != brief.feature_label
                    or list(existing.get("scope_items") or []) != list(brief.scope_items)
                ):
                    deps.tee.emit(
                        "error.raised",
                        {
                            "where": "dispatch",
                            "message": (
                                f"resume mismatch on {brief.agent_id}: "
                                f"feature/scope changed from spawn"
                            ),
                        },
                        iteration=iteration,
                        node="dispatch",
                        agent_id=brief.agent_id,
                    )
                    continue
                agents[brief.agent_id] = {
                    **existing,
                    "status": "active",
                    "last_invoked_at": iso_now(),
                    "invocation_count": existing.get("invocation_count", 0) + 1,
                }
                deps.tee.emit(
                    "agent.invoked",
                    {
                        "agent_id": brief.agent_id,
                        "dispatch_id": dispatch_id,
                        "brief_summary": brief.feature_label,
                        "attempt_budget": brief.budget.max_iterations,
                    },
                    iteration=iteration,
                    node="dispatch",
                    agent_id=brief.agent_id,
                    dispatch_id=dispatch_id,
                )

            bootstrap_dispatch(dispatch_paths)
            dispatch_paths.brief_json.write_text(brief.model_dump_json(indent=2))

            deps.tee.emit(
                "dispatch.scheduled",
                {
                    "dispatch_id": dispatch_id,
                    "agent_id": brief.agent_id,
                    "feature_label": brief.feature_label,
                    "item_names": list(brief.scope_items),
                    "brief_path": str(dispatch_paths.brief_json),
                },
                iteration=iteration,
                node="dispatch",
                agent_id=brief.agent_id,
                dispatch_id=dispatch_id,
            )

            agent_state: AgentState = {
                "agent_id": brief.agent_id,
                "feature_label": brief.feature_label,
                "scope_items": list(brief.scope_items),
                "work_dir": str(agent_paths.work_dir),
                "current_brief": brief,
                "attempt": 1,
                "stop_reason": None,
                "messages": [],
                "coverage_baseline": {
                    "timestamp": iso_now(),
                    "scope": "*",
                    "pct": 0.0,
                    "items_hit": 0,
                    "items_total": 0,
                    "detail": {},
                },
                "coverage_history": [],
                "proposed_status": {},
                "report": None,
            }
            new_dispatches.append(Send("agent_subgraph", agent_state))

        # Update orchestrator state for the iteration.
        return {
            "iteration": iteration,
            "agents": agents,
            "cycle": {
                "candidate_features": [],
                "in_flight": [
                    {
                        "agent_id": b.agent_id,
                        "dispatch_id": make_dispatch_id(iteration, i + 1),
                        "brief": b,
                    }
                    for i, b in enumerate(plan)
                ],
                "pending_results": [],
                "coverage_snapshot": None,
            },
            # Note: we return Send objects via __end__-style to LangGraph;
            # however to combine state update + Send list, we use a hybrid.
            # This is exposed via the extra key; LangGraph runtime picks it up
            # when this node returns Sends through the graph compile. See wiring.
            "_sends": new_dispatches,
        }

    return dispatch_node


def dispatch_send_router(state: dict) -> list:
    """Conditional edge whose return value is the list of Send objects."""
    cycle = state.get("cycle") or {}
    sends = state.get("_sends") or []
    if not sends:
        return []
    return list(sends)
