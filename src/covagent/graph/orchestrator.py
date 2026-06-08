"""Top-level graph wiring — INIT → LOOP (orchestrate ⇄ dispatch+agents+update_state) → FINALIZE."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from covagent.graph.agent_subgraph import build_agent_subgraph
from covagent.graph.deps import RuntimeDeps
from covagent.graph.nodes.dispatch import make_dispatch_node
from covagent.graph.nodes.finalize import make_finalize_node
from covagent.graph.nodes.init import make_init_node
from covagent.graph.nodes.orchestrate import make_orchestrate_node, orchestrate_route
from covagent.graph.nodes.update_state import make_update_state_node
from covagent.state.orchestrator import OrchestratorState


def build_orchestrator_graph(deps: RuntimeDeps):
    g = StateGraph(OrchestratorState)

    g.add_node("init", make_init_node(deps))
    g.add_node("orchestrate", make_orchestrate_node(deps))
    g.add_node("dispatch", make_dispatch_node(deps))
    g.add_node("agent_subgraph", _agent_runner(deps))
    g.add_node("update_state", make_update_state_node(deps))
    g.add_node("finalize", make_finalize_node(deps))

    g.add_edge(START, "init")
    g.add_edge("init", "orchestrate")
    g.add_conditional_edges(
        "orchestrate",
        orchestrate_route,
        {"dispatch": "dispatch", "finalize": "finalize"},
    )
    # `dispatch` returns a dict containing _sends; we route via a conditional
    # that emits Sends so each agent invocation runs in parallel.
    g.add_conditional_edges(
        "dispatch",
        _dispatch_to_sends,
        ["agent_subgraph"],
    )
    g.add_edge("agent_subgraph", "update_state")
    g.add_edge("update_state", "orchestrate")
    g.add_edge("finalize", END)

    return g.compile()


def _dispatch_to_sends(state: dict) -> Any:
    """Conditional edge: returns list of Send to materialize fan-out."""
    sends = state.get("_sends") or []
    return list(sends)


def _agent_runner(deps: RuntimeDeps):
    """Wrap the compiled agent subgraph so it produces a `pending_results` append.

    The compiled subgraph returns the final agent state (with `report`); the
    orchestrator only cares about a `GeneratorReturn` per result. We extract
    that and write it into `cycle.pending_results`.
    """
    subgraph = build_agent_subgraph(deps)

    def runner(agent_state: dict) -> dict:
        # Each Send invocation passes an AgentState.
        # The MemorySaver checkpointer keys per-thread; we use agent_id as thread.
        config = {"configurable": {"thread_id": agent_state["agent_id"]}}
        final = subgraph.invoke(agent_state, config)

        report = final.get("report")
        if report is None:
            return {"cycle": {"pending_results": []}}

        # Determine dispatch_id from work_dir or brief — store the latest one.
        # The brief was passed in current_brief.
        brief = agent_state.get("current_brief")
        dispatch_id = None
        if brief is not None:
            # Best effort — pull from agents/<id>/dispatches/* most-recent dir.
            from covagent.workspace.layout import AgentPaths

            ap = AgentPaths.for_agent(deps.run_paths, agent_state["agent_id"])
            if ap.dispatches_dir.exists():
                dispatches = sorted(ap.dispatches_dir.iterdir(), key=lambda p: p.name)
                if dispatches:
                    dispatch_id = dispatches[-1].name

        result = {
            "agent_id": agent_state["agent_id"],
            "dispatch_id": dispatch_id or "dispatch_unknown",
            "report": report,
        }
        return {"cycle": {"pending_results": [result]}}

    return runner
