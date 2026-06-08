"""On-disk layout helpers — run / agent / dispatch path scaffolding."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


def _short_hash(seed: str | None = None, n: int = 6) -> str:
    src = (seed or os.urandom(8).hex()).encode()
    return hashlib.sha1(src).hexdigest()[:n]


def _slugify(label: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", label).strip("_").lower()
    return s or "agent"


def make_run_id(now: datetime | None = None) -> str:
    now = now or datetime.now()
    return f"run_{now.strftime('%Y%m%d-%H%M%S')}_{_short_hash()}"


def make_agent_id(feature_label: str) -> str:
    return f"agent_{_slugify(feature_label)}_{_short_hash(feature_label, n=4)}"


def make_dispatch_id(iteration: int, seq: int) -> str:
    return f"dispatch_{iteration:03d}_{seq}"


@dataclass(frozen=True)
class RunPaths:
    workspace: Path
    run_id: str
    root: Path
    config_json: Path
    lockfile: Path
    testplan_dir: Path
    testplan_initial: Path
    testplan_snapshots: Path
    testplan_final: Path
    conversations_dir: Path
    init_conversation: Path
    orchestrate_conversation: Path
    agents_dir: Path
    coverage_dir: Path
    coverage_baseline: Path
    coverage_master: Path
    coverage_snapshots: Path
    coverage_reports: Path
    logs_dir: Path
    run_log: Path
    events_jsonl: Path
    summary_md: Path

    @classmethod
    def for_run(
        cls,
        workspace: Path,
        run_id: str,
        *,
        cov_ext: str = ".ucdb",
    ) -> RunPaths:
        ws = Path(workspace).resolve()
        root = ws / "runs" / run_id
        return cls(
            workspace=ws,
            run_id=run_id,
            root=root,
            config_json=root / "config.json",
            lockfile=root / "lockfile",
            testplan_dir=root / "testplan",
            testplan_initial=root / "testplan" / "initial.json",
            testplan_snapshots=root / "testplan" / "snapshots",
            testplan_final=root / "testplan" / "final.json",
            conversations_dir=root / "conversations",
            init_conversation=root / "conversations" / "init.json",
            orchestrate_conversation=root / "conversations" / "orchestrate.jsonl",
            agents_dir=root / "agents",
            coverage_dir=root / "coverage",
            coverage_baseline=root / "coverage" / f"baseline{cov_ext}",
            coverage_master=root / "coverage" / f"master{cov_ext}",
            coverage_snapshots=root / "coverage" / "snapshots",
            coverage_reports=root / "coverage" / "reports",
            logs_dir=root / "logs",
            run_log=root / "logs" / "run.log",
            events_jsonl=root / "logs" / "events.jsonl",
            summary_md=root / "summary.md",
        )

    @property
    def shared_rtl(self) -> Path:
        return self.workspace / "shared" / "rtl"

    @property
    def shared_spec(self) -> Path:
        return self.workspace / "shared" / "spec"


@dataclass(frozen=True)
class AgentPaths:
    run: RunPaths
    agent_id: str
    root: Path
    metadata_json: Path
    conversation_jsonl: Path
    checkpoint_dir: Path
    work_dir: Path
    tests_dir: Path
    dispatches_dir: Path

    @classmethod
    def for_agent(cls, run: RunPaths, agent_id: str) -> AgentPaths:
        root = run.agents_dir / agent_id
        return cls(
            run=run,
            agent_id=agent_id,
            root=root,
            metadata_json=root / "metadata.json",
            conversation_jsonl=root / "conversation.jsonl",
            checkpoint_dir=root / "checkpoint",
            work_dir=root / "work_dir",
            tests_dir=root / "work_dir" / "tests",
            dispatches_dir=root / "dispatches",
        )


@dataclass(frozen=True)
class DispatchPaths:
    agent: AgentPaths
    dispatch_id: str
    root: Path
    brief_json: Path
    return_json: Path
    sim_dir: Path
    coverage_dir: Path

    @classmethod
    def for_dispatch(
        cls, agent: AgentPaths, dispatch_id: str, *, cov_ext: str = ".ucdb"
    ) -> DispatchPaths:
        root = agent.dispatches_dir / dispatch_id
        return cls(
            agent=agent,
            dispatch_id=dispatch_id,
            root=root,
            brief_json=root / "brief.json",
            return_json=root / "return.json",
            sim_dir=root / "sim",
            coverage_dir=root / "coverage",
        )

    def coverage_delta(self, cov_ext: str) -> Path:
        return self.coverage_dir / f"delta{cov_ext}"


def bootstrap_run(run: RunPaths) -> None:
    for d in (
        run.root,
        run.testplan_dir,
        run.testplan_snapshots,
        run.conversations_dir,
        run.agents_dir,
        run.coverage_dir,
        run.coverage_snapshots,
        run.coverage_reports,
        run.logs_dir,
    ):
        d.mkdir(parents=True, exist_ok=True)
    run.lockfile.write_text(f"{os.getpid()}\n")


def bootstrap_agent(agent: AgentPaths) -> None:
    for d in (
        agent.root,
        agent.checkpoint_dir,
        agent.work_dir,
        agent.tests_dir,
        agent.dispatches_dir,
    ):
        d.mkdir(parents=True, exist_ok=True)


def bootstrap_dispatch(dispatch: DispatchPaths) -> None:
    for d in (dispatch.root, dispatch.sim_dir, dispatch.coverage_dir):
        d.mkdir(parents=True, exist_ok=True)
