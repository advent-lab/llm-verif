"""FINALIZE node — write final testplan, run summary, close out logs."""

from __future__ import annotations

from covagent.graph.deps import RuntimeDeps
from covagent.logging.events import iso_now


def make_finalize_node(deps: RuntimeDeps):
    def finalize_node(state: dict) -> dict:
        deps.tee.emit("node.entered", {"node": "finalize"}, node="finalize")

        plan = state["testplan"]
        deps.run_paths.testplan_final.write_text(plan.model_dump_json(indent=2))

        agents = state.get("agents") or {}
        dispatch_log = state.get("dispatch_log") or []

        cov_summary = (
            deps.simulator.parse_coverage(deps.run_paths.coverage_master, deps.config.mode)
            if deps.run_paths.coverage_master.exists()
            else None
        )
        cov_line = (
            f"Coverage: {cov_summary.overall_pct:.1f}% "
            f"({cov_summary.items_hit}/{cov_summary.items_total})"
            if cov_summary
            else "Coverage: not collected"
        )

        # Markdown summary.
        lines = [
            f"# Run summary — {deps.run_id}",
            "",
            f"- Design: {deps.config.design_name}",
            f"- Mode: {deps.config.mode}",
            f"- Simulator: {deps.config.simulator}",
            f"- Iterations: {state.get('iteration', 0)}",
            f"- Dispatches: {len(dispatch_log)}",
            f"- Agents: {len(agents)}",
            f"- Run status: {state.get('run_status', 'unknown')}",
            f"- Finalized at: {iso_now()}",
            "",
            f"## {cov_line}",
            "",
            "## Agents",
        ]
        for aid, am in agents.items():
            lines.append(
                f"- `{aid}` — feature={am.get('feature_label')} "
                f"status={am.get('status')} invocations={am.get('invocation_count')}"
            )
        lines.extend(["", "## Dispatch log", ""])
        for d in dispatch_log:
            lines.append(
                f"- {d.get('dispatch_id')} (iter {d.get('iteration')}): "
                f"agent={d.get('agent_id')} return={d.get('return_summary')}"
            )

        deps.run_paths.summary_md.write_text("\n".join(lines) + "\n")

        # Remove lockfile.
        if deps.run_paths.lockfile.exists():
            deps.run_paths.lockfile.unlink()

        deps.tee.emit(
            "run.ended",
            {
                "run_status": state.get("run_status", "done"),
                "iterations": state.get("iteration", 0),
                "total_dispatches": len(dispatch_log),
                "wall_time_s": 0.0,
            },
        )
        deps.tee.emit("node.exited", {"node": "finalize"}, node="finalize")
        return {"run_status": state.get("run_status", "done")}

    return finalize_node
