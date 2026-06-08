"""ORCHESTRATE node — persistent project-manager LLM, emits OrchestratorAction."""

from __future__ import annotations

import time
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from covagent.graph.deps import RuntimeDeps
from covagent.graph.nodes._inventory import file_inventory
from covagent.logging.conversations import ConversationLogger
from covagent.prompts import render
from covagent.state.dispatch import (
    DispatchBrief,
    DispatchPlan,
    OrchestratorAction,
    RouteDecision,
)
from covagent.state.testplan import Testplan
from covagent.tools import ToolContext, tools_for_orchestrate


# Pydantic schemas for structured output (LLMs emit these via with_structured_output)


class _OrchestratorActionPydantic(BaseModel):
    """LLM-facing schema for OrchestratorAction. Mirrors state/dispatch.py.

    `kind` defaults to 'terminate' so a malformed / empty LLM response
    fails safe (loop exits) rather than crashing the run.
    """

    kind: str = Field(default="terminate", description="'dispatch' or 'terminate'")
    dispatch_briefs: list[DispatchBrief] = Field(default_factory=list)
    rationale: str = ""
    route_run_status: str | None = "blocked"
    route_reason: str | None = "no structured response"


def _to_typed_action(p: _OrchestratorActionPydantic) -> OrchestratorAction:
    if p.kind == "dispatch":
        plan: DispatchPlan = {"briefs": p.dispatch_briefs}
        return {"kind": "dispatch", "dispatch_plan": plan, "route_decision": None}
    rd: RouteDecision = {
        "reason": p.route_run_status or "done",  # type: ignore[typeddict-item]
        "summary": p.route_reason or "",
    }
    return {"kind": "terminate", "dispatch_plan": None, "route_decision": rd}


def make_orchestrate_node(deps: RuntimeDeps):
    def orchestrate_node(state: dict) -> dict:
        deps.tee.emit(
            "node.entered",
            {"node": "orchestrate", "iteration": state.get("iteration", 0)},
            iteration=state.get("iteration"),
            node="orchestrate",
        )
        t0 = time.monotonic()

        plan_ref: list[Testplan] = [state["testplan"]]
        agents_ref: list[dict] = [dict(state.get("agents") or {})]
        dispatch_log_ref: list[list] = [list(state.get("dispatch_log") or [])]

        ctx = ToolContext(
            run_id=deps.run_id,
            conversation="orchestrate",
            iteration=state.get("iteration"),
            node="orchestrate",
            design_root=deps.design_root,
            simulator=deps.simulator,
            coverage_master=deps.run_paths.coverage_master,
            coverage_mode=deps.config.mode,
            testplan_ref=plan_ref,
            agents_ref=agents_ref,
            dispatch_log_ref=dispatch_log_ref,
            emit=deps.tee.emit,
        )

        history: list[BaseMessage] = list(state.get("messages") or [])
        if not history:
            inv = file_inventory(deps.design_entry)
            sys_text = render(
                "orchestrate",
                max_iterations=deps.config.budget.max_iterations,
                max_dispatches=deps.config.budget.max_dispatches,
                **inv,
            )
            opener = (
                f"Run starting. Mode: {deps.config.mode}. "
                f"Design: {deps.config.design_name}.\n"
                f"design_digest:\n{state.get('design_digest', '')[:4000]}\n\n"
                f"Initial testplan installed. Begin orchestrating."
            )
            history = [SystemMessage(content=sys_text), HumanMessage(content=opener)]

        # Tool ReAct loop — orchestrate may call read tools, patch testplan, etc.
        tools = tools_for_orchestrate(ctx)
        from langgraph.prebuilt import ToolNode

        tool_node = ToolNode(tools)
        model_with_tools = deps.llm.get("orchestrate").bind_tools(tools)

        max_tool_turns = 6
        for _ in range(max_tool_turns):
            ai = model_with_tools.invoke(history)
            history.append(ai)
            if not getattr(ai, "tool_calls", None):
                break
            tn_result = tool_node.invoke({"messages": history})
            history.extend(tn_result["messages"])

        # Now ask for structured action.
        structured = deps.llm.get("orchestrate").with_structured_output(
            _OrchestratorActionPydantic
        )
        history.append(
            HumanMessage(
                content=(
                    "Now emit your OrchestratorAction. "
                    "If continuing, kind='dispatch' with dispatch_briefs populated. "
                    "If terminating, kind='terminate' with route_run_status and route_reason."
                )
            )
        )
        action_raw: _OrchestratorActionPydantic = structured.invoke(history)
        action = _to_typed_action(action_raw)

        # Append a record of the action to the persistent conversation as an AI turn.
        history.append(
            AIMessage(content=f"[action] kind={action['kind']} rationale={action_raw.rationale}")
        )

        # Persist orchestrate conversation in append mode (full history each turn is fine
        # at this scale; switch to incremental append if it becomes a hotspot).
        clog = ConversationLogger(deps.run_paths.orchestrate_conversation, kind="orchestrate")
        # Append only the last turn (whichever was newly added) — but for simplicity
        # we re-append everything that wasn't there before. Simpler: just append the
        # last AI summary line.
        clog.append(history[-1])

        update: dict[str, Any] = {
            "messages": history[len(state.get("messages") or []):],  # only the new tail
            "testplan": plan_ref[0],
            "agents": agents_ref[0],
            "dispatch_log": dispatch_log_ref[0],
            "cycle": {
                "candidate_features": [],
                "in_flight": [],
                "pending_results": [],
                "coverage_snapshot": None,
                "pending_action": action,
            },
        }

        duration_s = time.monotonic() - t0
        deps.tee.emit(
            "node.exited",
            {"node": "orchestrate", "duration_s": duration_s},
            iteration=state.get("iteration"),
            node="orchestrate",
        )
        return update

    return orchestrate_node


def orchestrate_route(state: dict) -> str:
    """Conditional edge: dispatch | finalize."""
    cycle = state.get("cycle") or {}
    action = cycle.get("pending_action") or {}
    if action.get("kind") == "dispatch":
        return "dispatch"
    return "finalize"
