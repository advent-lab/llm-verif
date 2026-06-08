"""End-to-end smoke test: full graph with mock LLM + mock simulator + tiny design."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from covagent.config import Budget, CoverageGoal, ModelConfig, RunConfig
from covagent.graph.deps import RuntimeDeps
from covagent.graph.llm_provider import MockLLMProvider
from covagent.graph.orchestrator import build_orchestrator_graph
from covagent.logging.events import EventLogger
from covagent.logging.run_log import RunLogRenderer, TeeLogger
from covagent.simulators import get_adapter
from covagent.state.testplan import Testplan
from covagent.workspace.layout import RunPaths, bootstrap_run, make_run_id


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws


@pytest.fixture
def fake_dashboard(tmp_path: Path) -> Path:
    rtl_dir = tmp_path / "design" / "rtl"
    rtl_dir.mkdir(parents=True)
    (rtl_dir / "lfsr.sv").write_text("module lfsr; endmodule\n")
    spec_dir = tmp_path / "design" / "docs"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# LFSR\nResets to seed.\n")

    dash = {
        "lfsr": {
            "design": [str(rtl_dir / "lfsr.sv")],
            "design_context": [],
            "spec": str(spec_dir / "spec.md"),
        }
    }
    p = tmp_path / "dashboard.json"
    p.write_text(json.dumps(dash))
    return p


def _terminate_msg() -> AIMessage:
    return AIMessage(content=json.dumps({
        "kind": "terminate",
        "dispatch_briefs": [],
        "rationale": "done",
        "route_run_status": "done",
        "route_reason": "test terminate",
    }))


def _dispatch_msg() -> AIMessage:
    brief = {
        "agent_id": "agent_test_aaaa",
        "feature_label": "test_feat",
        "scope_items": ["t1"],
        "instructions": "do it",
        "rtl_context": [],
        "spec_excerpts": [],
        "baseline_coverage": {},
        "goal": {"type": "absolute", "target": {"pct": 0}},
        "budget": {"max_iterations": 2, "max_tokens": None},
        "items_context": [{
            "target_type": "testpoint",
            "name": "t1",
            "description": "test",
            "history": [],
            "instructions": "",
            "coverage": None,
        }],
    }
    return AIMessage(content=json.dumps({
        "kind": "dispatch",
        "dispatch_briefs": [brief],
        "rationale": "first round",
    }))


def test_run_terminates_immediately(workspace: Path, fake_dashboard: Path) -> None:
    """Mock provider with default scripts → terminate at first orchestrate."""
    config = RunConfig(
        workspace=workspace,
        design_name="lfsr",
        dashboard_path=fake_dashboard,
        mode="functional",
        simulator="mock",
        goal=CoverageGoal(),
        budget=Budget(max_iterations=2, max_dispatches=2),
        models=ModelConfig(),
    )
    sim = get_adapter("mock")
    run_id = make_run_id()
    rp = RunPaths.for_run(workspace, run_id, cov_ext=sim.extension())
    bootstrap_run(rp)
    rp.coverage_baseline.write_bytes(b"")

    el = EventLogger(rp.events_jsonl, run_id=run_id)
    rl = RunLogRenderer(rp.run_log)
    tee = TeeLogger(el, rl)

    deps = RuntimeDeps(
        config=config,
        run_id=run_id,
        run_paths=rp,
        simulator=sim,
        llm=MockLLMProvider(),
        tee=tee,
    )
    graph = build_orchestrator_graph(deps)
    final = graph.invoke({
        "config": config,
        "run_id": run_id,
        "design_digest": None,
        "testplan": Testplan(mode="functional"),
        "dispatch_log": [],
        "agents": {},
        "iteration": 0,
        "run_status": "init",
        "messages": [],
        "cycle": {"candidate_features": [], "in_flight": [],
                  "pending_results": [], "coverage_snapshot": None},
    }, {"recursion_limit": 50})
    tee.close()

    assert rp.testplan_final.exists()
    assert rp.summary_md.exists()
    assert final["iteration"] == 0
    assert len(final.get("dispatch_log") or []) == 0


def test_run_completes_one_dispatch(workspace: Path, fake_dashboard: Path) -> None:
    """Script orchestrate to dispatch once then terminate. Validates full loop."""
    config = RunConfig(
        workspace=workspace,
        design_name="lfsr",
        dashboard_path=fake_dashboard,
        mode="functional",
        simulator="mock",
        goal=CoverageGoal(),
        budget=Budget(max_iterations=2, max_dispatches=2),
        models=ModelConfig(),
    )
    sim = get_adapter("mock")
    run_id = make_run_id()
    rp = RunPaths.for_run(workspace, run_id, cov_ext=sim.extension())
    bootstrap_run(rp)
    rp.coverage_baseline.write_bytes(b"")

    el = EventLogger(rp.events_jsonl, run_id=run_id)
    rl = RunLogRenderer(rp.run_log)
    tee = TeeLogger(el, rl)

    # Script orchestrate: tool-loop turn (empty), dispatch, then on iter 2: tool-loop turn, terminate.
    # Each call to .get() resets the script — the structured-output call also re-fetches.
    # We give a "long enough" script so any call sees a usable response.
    llm = MockLLMProvider()
    llm.set_script("orchestrate", [
        AIMessage(content=""),       # tool-loop turn 1
        _dispatch_msg(),             # structured action 1
        AIMessage(content=""),       # tool-loop turn 2
        _terminate_msg(),            # structured action 2
    ])
    # init: no tool calls; just a final digest text.
    llm.set_script("init", [AIMessage(content="LFSR design digest")])

    deps = RuntimeDeps(
        config=config,
        run_id=run_id,
        run_paths=rp,
        simulator=sim,
        llm=llm,
        tee=tee,
    )
    # Pre-seed a testpoint so update_state has something to patch.
    plan = Testplan(
        mode="functional",
        testpoints=[{"name": "t1", "description": "reset"}],  # type: ignore[list-item]
    )

    graph = build_orchestrator_graph(deps)
    final = graph.invoke({
        "config": config,
        "run_id": run_id,
        "design_digest": None,
        "testplan": plan,
        "dispatch_log": [],
        "agents": {},
        "iteration": 0,
        "run_status": "init",
        "messages": [],
        "cycle": {"candidate_features": [], "in_flight": [],
                  "pending_results": [], "coverage_snapshot": None},
    }, {"recursion_limit": 50})
    tee.close()

    # Validations: full dispatch fired, testplan was patched, agent registered.
    assert rp.testplan_final.exists()
    assert rp.summary_md.exists()
    assert final["iteration"] == 1
    assert len(final["dispatch_log"]) == 1
    assert "agent_test_aaaa" in final["agents"]
    final_plan = final["testplan"]
    assert final_plan.testpoints[0].owner_agent_id == "agent_test_aaaa"
    assert len(final_plan.testpoints[0].history) == 1
