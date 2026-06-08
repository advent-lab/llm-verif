"""UPDATE_STATE node — deterministic merge + reconciliation + summary turn."""

from __future__ import annotations

import time
from typing import Any

from langchain_core.messages import HumanMessage

from covagent.coverage.merge import merge_deltas
from covagent.coverage.snapshot import take_snapshot
from covagent.graph.deps import RuntimeDeps
from covagent.logging.events import iso_now
from covagent.state.testplan import HistoryEntry
from covagent.tools import ToolContext
from covagent.tools.testplan import append_history, patch_testplan
from covagent.workspace.layout import AgentPaths, DispatchPaths


def make_update_state_node(deps: RuntimeDeps):
    def update_state_node(state: dict) -> dict:
        deps.tee.emit(
            "node.entered",
            {"node": "update_state", "iteration": state.get("iteration", 0)},
            iteration=state.get("iteration"),
            node="update_state",
        )
        t0 = time.monotonic()

        cycle = dict(state.get("cycle") or {})
        results = list(cycle.get("pending_results") or [])
        agents: dict = dict(state.get("agents") or {})
        new_log_entries: list = []
        plan_ref = [state["testplan"]]
        iteration = state.get("iteration", 0)

        # Collect deltas from results' dispatch dirs.
        deltas: list = []
        for r in results:
            agent_id = r.get("agent_id")
            dispatch_id = r.get("dispatch_id")
            if not agent_id or not dispatch_id:
                continue
            ap = AgentPaths.for_agent(deps.run_paths, agent_id)
            dp = DispatchPaths.for_dispatch(ap, dispatch_id)
            delta_path = dp.coverage_dir / f"delta{deps.simulator.extension()}"
            if delta_path.exists():
                deltas.append(delta_path)

        merge_t0 = time.monotonic()
        merge_result = merge_deltas(
            deps.simulator,
            deps.run_paths.coverage_master,
            deltas,
            baseline=deps.run_paths.coverage_baseline,
        )
        merge_dur = time.monotonic() - merge_t0
        if merge_result.ok:
            deps.tee.emit(
                "coverage.merged",
                {
                    "master_path": str(deps.run_paths.coverage_master),
                    "delta_count": len(deltas),
                    "duration_s": round(merge_dur, 4),
                },
                iteration=iteration,
                node="update_state",
            )
        else:
            deps.tee.emit(
                "warning.raised",
                {
                    "where": "update_state",
                    "message": f"merge failed: {merge_result.error}",
                },
                iteration=iteration,
                node="update_state",
            )

        # Snapshot.
        snap_path = take_snapshot(
            deps.run_paths.coverage_master,
            deps.run_paths.coverage_snapshots,
            iteration,
        )
        deps.tee.emit(
            "coverage.snapshot_taken",
            {"path": str(snap_path), "iteration": iteration},
            iteration=iteration,
            node="update_state",
        )

        # Reconcile each result against ground truth + apply routine patches.
        ctx = ToolContext(
            run_id=deps.run_id,
            conversation="orchestrate",
            iteration=iteration,
            node="update_state",
            simulator=deps.simulator,
            coverage_master=deps.run_paths.coverage_master,
            coverage_mode=deps.config.mode,
            testplan_ref=plan_ref,
            emit=deps.tee.emit,
        )

        cov_summary = (
            deps.simulator.parse_coverage(deps.run_paths.coverage_master, deps.config.mode)
            if deps.run_paths.coverage_master.exists()
            else None
        )

        per_dispatch_lines: list[str] = []

        for r in results:
            agent_id = r["agent_id"]
            dispatch_id = r["dispatch_id"]
            report = r["report"]
            # Update agent metadata.
            am = agents.get(agent_id)
            if am is not None:
                # Mark idle if all scope_items have history-recorded outcome=passed
                # and proposed status==complete. Pragmatic: if all proposals say complete, mark idle.
                proposals = {ir.name: ir.proposed_status for ir in report.items}
                all_complete = (
                    proposals
                    and all(
                        proposals.get(it) == "complete"
                        for it in am.get("scope_items") or []
                    )
                )
                am["status"] = "idle" if all_complete else "active"
                if all_complete:
                    deps.tee.emit(
                        "agent.signed_off",
                        {"agent_id": agent_id, "reason": "all scope_items complete"},
                        iteration=iteration,
                        node="update_state",
                        agent_id=agent_id,
                    )
                agents[agent_id] = am

            # Apply routine patches per item.
            for ir in report.items:
                # Append history.
                append_history(
                    ctx,
                    target_type=ir.target_type,
                    name=ir.name,
                    outcome="passed" if ir.proposed_status == "complete" else "partial",
                    summary=ir.summary or f"dispatch {dispatch_id}",
                    artifacts_path=None,
                    agent_id=agent_id,
                )
                # Patch status — claim agrees with truth?  For mock/scaffolding, trust proposal.
                patch_testplan(
                    ctx,
                    target_type=ir.target_type,
                    name=ir.name,
                    fields={"status": ir.proposed_status, "owner_agent_id": agent_id},
                )

            new_log_entries.append(
                {
                    "dispatch_id": dispatch_id,
                    "iteration": iteration,
                    "feature": report.feature_label,
                    "item_names": [ir.name for ir in report.items],
                    "agent_id": agent_id,
                    "brief_summary": report.feature_label,
                    "return_summary": (
                        f"stop={report.stop_reason} items={len(report.items)}"
                    ),
                    "work_dir": str(AgentPaths.for_agent(deps.run_paths, agent_id).work_dir),
                    "timestamp": iso_now(),
                }
            )
            deps.tee.emit(
                "dispatch.completed",
                {
                    "dispatch_id": dispatch_id,
                    "agent_id": agent_id,
                    "stop_reason": report.stop_reason,
                    "wall_time_s": 0.0,
                },
                iteration=iteration,
                node="update_state",
                agent_id=agent_id,
                dispatch_id=dispatch_id,
            )
            per_dispatch_lines.append(
                f"- {dispatch_id} ({agent_id}): stop={report.stop_reason}, "
                f"items={[ir.name + '/' + ir.proposed_status for ir in report.items]}"
            )

        # Snapshot testplan.
        snap_tp = deps.run_paths.testplan_snapshots / f"iter_{iteration:03d}.json"
        snap_tp.write_text(plan_ref[0].model_dump_json(indent=2))
        deps.tee.emit(
            "testplan.snapshot_written",
            {"path": str(snap_tp), "iteration": iteration},
            iteration=iteration,
            node="update_state",
        )

        # Build summary turn for orchestrate.
        cov_line = (
            f"coverage[*] = {cov_summary.overall_pct:.1f}% "
            f"({cov_summary.items_hit}/{cov_summary.items_total})"
            if cov_summary
            else "coverage: master DB absent"
        )
        summary_text = (
            f"[update_state @ iter {iteration}]\n"
            f"{cov_line}\n"
            f"Dispatches:\n" + "\n".join(per_dispatch_lines or ["(none)"])
        )

        duration_s = time.monotonic() - t0
        deps.tee.emit(
            "node.exited",
            {"node": "update_state", "duration_s": duration_s},
            iteration=iteration,
            node="update_state",
        )

        return {
            "testplan": plan_ref[0],
            "agents": agents,
            "dispatch_log": new_log_entries,  # reducer appends to existing log
            "messages": [HumanMessage(content=summary_text)],
            "cycle": {
                "candidate_features": [],
                "in_flight": [],
                "pending_results": [],
                "coverage_snapshot": None,
            },
        }

    return update_state_node
