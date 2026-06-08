"""Persistent agent subgraph — init → plan → act → check → finish (PAUSE).

Compiled once with a checkpointer keyed by `agent_id`. State persists across
dispatches: `messages` grows, `coverage_history` accumulates, `work_dir`
files persist.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from covagent.graph.deps import RuntimeDeps
from covagent.logging.events import iso_now
from covagent.prompts import render
from covagent.state.agent import AgentState, CoverageSnapshot
from covagent.state.dispatch import (
    DispatchBrief,
    GeneratorReport,
    ItemReport,
    StopReason,
)
from covagent.tools import ToolContext, tools_for_agent_act, tools_for_agent_plan


class AttemptPlan(BaseModel):
    """plan node's structured output."""

    target_items: list[str] = Field(default_factory=list)
    approach: str = ""
    expected_files: list[str] = Field(default_factory=list)


_PLATEAU_EPS = 1.0
_PLATEAU_N = 3


def _ctx_for(deps: RuntimeDeps, state: AgentState, *, node: str) -> ToolContext:
    design_files: list[Path] = []
    if deps.design_entry is not None:
        design_files = list(deps.design_entry.design) + list(deps.design_entry.design_context)
    return ToolContext(
        run_id=deps.run_id,
        conversation="agent",
        node=node,
        agent_id=state["agent_id"],
        work_dir=Path(state["work_dir"]),
        design_root=deps.design_root,
        simulator=deps.simulator,
        coverage_master=deps.run_paths.coverage_master,
        coverage_mode=deps.config.mode,
        design_files=design_files,
        emit=deps.tee.emit,
    )


def _coverage_snapshot(deps: RuntimeDeps, scope: str = "*") -> CoverageSnapshot:
    if not deps.run_paths.coverage_master.exists():
        return {
            "timestamp": iso_now(),
            "scope": scope,
            "pct": 0.0,
            "items_hit": 0,
            "items_total": 0,
            "detail": {},
        }
    summary = deps.simulator.parse_coverage(deps.run_paths.coverage_master, deps.config.mode)
    return {
        "timestamp": iso_now(),
        "scope": scope,
        "pct": summary.overall_pct,
        "items_hit": summary.items_hit,
        "items_total": summary.items_total,
        "detail": dict(summary.breakdown),
    }


def make_agent_init(deps: RuntimeDeps):
    def agent_init(state: AgentState) -> dict:
        is_spawn = not state.get("messages")
        brief: DispatchBrief | None = state.get("current_brief")
        if brief is None:
            raise ValueError("agent_init: state.current_brief is required")

        baseline = _coverage_snapshot(deps)
        update: dict[str, Any] = {
            "attempt": 1,
            "stop_reason": None,
            "proposed_status": {},
            "coverage_baseline": baseline,
        }

        if is_spawn:
            sys_text = render(
                "agent_act",
                feature_label=state["feature_label"],
            )
            opener = (
                f"You are activated for dispatch on feature `{state['feature_label']}`.\n"
                f"Brief:\n{json.dumps(brief.model_dump(), indent=2, default=str)}"
            )
            new_msgs: list[BaseMessage] = [
                SystemMessage(content=sys_text),
                HumanMessage(content=opener),
            ]
            # Note: agent.spawned/invoked events are emitted by the dispatch node,
            # which has the iteration context; agent_init must not duplicate them.
        else:
            opener = (
                f"New dispatch — brief:\n{json.dumps(brief.model_dump(), indent=2, default=str)}"
            )
            new_msgs = [HumanMessage(content=opener)]

        update["messages"] = new_msgs
        return update

    return agent_init


def make_plan_node(deps: RuntimeDeps):
    def plan_node(state: AgentState) -> dict:
        ctx = _ctx_for(deps, state, node="plan")
        tools = tools_for_agent_plan(ctx)
        model = deps.llm.get("agent").bind_tools(tools)
        tool_node = ToolNode(tools)

        sys_text = render(
            "agent_plan",
            feature_label=state["feature_label"],
            scope_items=list(state["scope_items"]),
        )
        # Replace the existing system message at index 0 with plan-flavored
        # version for this turn — keep all other history.
        history = list(state["messages"])
        if history and isinstance(history[0], SystemMessage):
            history[0] = SystemMessage(content=sys_text)
        else:
            history = [SystemMessage(content=sys_text), *history]

        original_len = len(state["messages"])
        max_turns = 4
        for _ in range(max_turns):
            ai = model.invoke(history)
            history.append(ai)
            if not getattr(ai, "tool_calls", None):
                break
            results = tool_node.invoke({"messages": history})
            history.extend(results["messages"])

        return {"messages": history[original_len:]}

    return plan_node


def make_act_llm_node(deps: RuntimeDeps):
    def act_llm(state: AgentState) -> dict:
        ctx = _ctx_for(deps, state, node="act")
        tools = tools_for_agent_act(ctx)
        model = deps.llm.get("agent").bind_tools(tools)

        sys_text = render("agent_act", feature_label=state["feature_label"])
        history = list(state["messages"])
        if history and isinstance(history[0], SystemMessage):
            history[0] = SystemMessage(content=sys_text)
        else:
            history = [SystemMessage(content=sys_text), *history]

        ai = model.invoke(history)
        return {"messages": [ai]}

    return act_llm


def make_act_tools_node(deps: RuntimeDeps):
    """ToolNode that executes whatever tools_for_agent_act exposes."""

    def act_tools(state: AgentState) -> dict:
        ctx = _ctx_for(deps, state, node="act")
        tn = ToolNode(tools_for_agent_act(ctx))
        return tn.invoke(state)

    return act_tools


def _act_route(state: AgentState) -> Literal["act_tools", "check"]:
    msgs = state.get("messages") or []
    if not msgs:
        return "check"
    last = msgs[-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return "act_tools"
    return "check"


def make_check_node(deps: RuntimeDeps):
    def check(state: AgentState) -> dict:
        snap = _coverage_snapshot(deps)
        history = list(state.get("coverage_history", []))
        history_with_new = history + [snap]

        baseline = state.get("coverage_baseline") or snap
        budget = state["current_brief"].budget if state.get("current_brief") else None
        attempt = state.get("attempt", 1)

        stop: StopReason | None = None

        # 1) budget
        if budget is not None and attempt >= budget.max_iterations:
            stop = "budget"
        # 2) goal — interpret simply: scope pct >= target.target.pct
        if stop is None and state.get("current_brief"):
            goal = state["current_brief"].goal
            target_pct = goal.target.get("pct") if isinstance(goal.target, dict) else None
            if target_pct is not None and snap["pct"] >= float(target_pct):
                stop = "goal"
        # 3) plateau — last N deltas all < eps from baseline
        if stop is None and len(history_with_new) >= _PLATEAU_N:
            deltas = [
                history_with_new[i]["pct"] - history_with_new[i - 1]["pct"]
                for i in range(len(history_with_new) - _PLATEAU_N + 1, len(history_with_new))
            ]
            if all(d < _PLATEAU_EPS for d in deltas):
                stop = "plateau"

        update: dict[str, Any] = {
            "coverage_history": [snap],
            "attempt": attempt + 1,
            "stop_reason": stop,
        }
        return update

    return check


def _check_route(state: AgentState) -> Literal["plan", "finish"]:
    return "finish" if state.get("stop_reason") else "plan"


def make_finish_node(deps: RuntimeDeps):
    def finish(state: AgentState) -> dict:
        brief = state["current_brief"]
        baseline = state.get("coverage_baseline") or {}
        history = state.get("coverage_history") or []
        latest = history[-1] if history else baseline

        # Derive proposed_status: items the brief touched, default to incomplete.
        proposed: dict[str, str] = dict(state.get("proposed_status") or {})
        if brief is not None:
            for item in brief.scope_items:
                proposed.setdefault(item, "incomplete")

        items: list[ItemReport] = []
        if brief is not None:
            for ic in brief.items_context:
                items.append(
                    ItemReport(
                        name=ic.name,
                        target_type=ic.target_type,
                        proposed_status=proposed.get(ic.name, "incomplete"),  # type: ignore[arg-type]
                        summary="",
                        coverage={"pct": latest.get("pct", 0.0)} if latest else None,
                    )
                )

        report = GeneratorReport(
            agent_id=state["agent_id"],
            feature_label=state["feature_label"],
            items=items,
            stop_reason=state.get("stop_reason") or "budget",
        )
        return {"report": report, "proposed_status": proposed}

    return finish


def build_agent_subgraph(deps: RuntimeDeps):
    g = StateGraph(AgentState)
    g.add_node("agent_init", make_agent_init(deps))
    g.add_node("plan", make_plan_node(deps))
    g.add_node("act", make_act_llm_node(deps))
    g.add_node("act_tools", make_act_tools_node(deps))
    g.add_node("check", make_check_node(deps))
    g.add_node("finish", make_finish_node(deps))

    g.add_edge(START, "agent_init")
    g.add_edge("agent_init", "plan")
    g.add_edge("plan", "act")
    g.add_conditional_edges("act", _act_route, {"act_tools": "act_tools", "check": "check"})
    g.add_edge("act_tools", "act")
    g.add_conditional_edges("check", _check_route, {"plan": "plan", "finish": "finish"})
    g.add_edge("finish", END)

    return g.compile(checkpointer=MemorySaver())
