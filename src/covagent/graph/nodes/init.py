"""INIT node — builds the initial testplan + design_digest, then hands off."""

from __future__ import annotations

import json
import time
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from covagent.graph.deps import RuntimeDeps
from covagent.graph.nodes._inventory import file_inventory
from covagent.logging.conversations import ConversationLogger
from covagent.logging.events import iso_now
from covagent.prompts import render
from covagent.state.testplan import Testplan
from covagent.tools import ToolContext, tools_for_init


def make_init_node(deps: RuntimeDeps):
    def init_node(state: dict) -> dict:
        deps.tee.emit("node.entered", {"node": "init", "iteration": 0}, node="init")
        t0 = time.monotonic()

        # Plan ref seeded with whatever the caller passed in (often empty for
        # production runs; in tests / replay flows it may already be populated).
        # build_testplan tool overwrites it; if the LLM never calls build_testplan
        # the existing plan is preserved.
        seeded = state.get("testplan") or Testplan(mode=deps.config.mode)
        plan_ref: list[Testplan] = [seeded]
        ctx = ToolContext(
            run_id=deps.run_id,
            conversation="init",
            node="init",
            design_root=deps.design_root,
            simulator=deps.simulator,
            coverage_master=deps.run_paths.coverage_master,
            coverage_mode=deps.config.mode,
            testplan_ref=plan_ref,
            emit=deps.tee.emit,
        )

        inv = file_inventory(deps.design_entry)
        sys_text = render(
            "init",
            mode=deps.config.mode,
            design_name=deps.config.design_name,
            **inv,
        )
        opener = (
            "Build the initial testplan now. Read RTL and spec as needed, "
            "then call build_testplan, then emit the design_digest."
        )

        tools = tools_for_init(ctx)
        model = deps.llm.get("init").bind_tools(tools)
        history: list[Any] = [SystemMessage(content=sys_text), HumanMessage(content=opener)]

        # Bounded ReAct loop — init should converge in a handful of turns.
        from langgraph.prebuilt import ToolNode  # local import — avoid module-level cost

        tool_node = ToolNode(tools)
        max_turns = 6
        for _ in range(max_turns):
            ai = model.invoke(history)
            history.append(ai)
            if not getattr(ai, "tool_calls", None):
                break
            # Execute tool calls.
            tool_state = {"messages": history}
            tn_result = tool_node.invoke(tool_state)
            history.extend(tn_result["messages"])

        # Persist init conversation transcript.
        ConversationLogger(deps.run_paths.init_conversation, kind="init").write_initial(history)

        # Pull design_digest from the last AI message text content.
        design_digest = ""
        for m in reversed(history):
            if isinstance(m, AIMessage) and m.content:
                design_digest = m.content if isinstance(m.content, str) else json.dumps(m.content)
                break

        # If LLM didn't call build_testplan and seed was empty, log a warning.
        if (
            not plan_ref[0].testpoints
            and not plan_ref[0].covergroups
            and not plan_ref[0].code_scopes
        ):
            deps.tee.emit(
                "warning.raised",
                {"where": "init", "message": "build_testplan was not called; plan is empty"},
                node="init",
            )

        deps.run_paths.testplan_initial.write_text(plan_ref[0].model_dump_json(indent=2))

        duration_s = time.monotonic() - t0
        deps.tee.emit("node.exited", {"node": "init", "duration_s": duration_s}, node="init")

        return {
            "testplan": plan_ref[0],
            "design_digest": design_digest,
            "run_status": "running",
            "iteration": 0,
        }

    return init_node
