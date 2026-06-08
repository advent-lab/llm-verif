"""covagent CLI.

Configuration sources (highest priority wins):
    1. CLI flags (e.g. `--design lfsr`)
    2. Environment / `.env` file (e.g. `COVAGENT_DESIGN=lfsr`)
    3. Built-in defaults

Run `covagent show-config` to inspect the merged config without launching.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import click

from covagent.graph.deps import RuntimeDeps
from covagent.graph.llm_provider import OpenAILLMProvider, MockLLMProvider
from covagent.graph.orchestrator import build_orchestrator_graph
from covagent.logging.events import EventLogger
from covagent.logging.run_log import RunLogRenderer, TeeLogger
from covagent.settings import (
    build_run_config,
    get_openai_api_key,
    get_openai_base_url,
    get_questa_path,
    load_dotenv_file,
    use_mock_llm_default,
)
from covagent.simulators import get_adapter
from covagent.simulators._questa_helpers import DEFAULT_SIM_PATH
from covagent.state.testplan import Testplan
from covagent.workspace.dashboard import get_design
from covagent.workspace.layout import RunPaths, bootstrap_run, make_run_id


def _common_options(f):
    """Decorator bundling the config-override flags shared by `run` and `show-config`."""
    decorators = [
        click.option("--env-file", type=click.Path(path_type=Path), default=None,
                     help="Path to a .env file (default: ./.env)."),
        click.option("--design", default=None, help="Design name (key in dashboard.json)."),
        click.option("--dashboard", type=click.Path(path_type=Path), default=None),
        click.option("--workspace", type=click.Path(path_type=Path), default=None),
        click.option("--mode", type=click.Choice(["functional", "code"]), default=None),
        click.option("--simulator", type=click.Choice(["mock", "questa", "verilator"]), default=None),
        click.option("--max-iterations", type=int, default=None),
        click.option("--max-dispatches", type=int, default=None),
        click.option("--goal-pct", type=float, default=None),
        click.option("--orchestrator-model", default=None),
        click.option("--agent-model", default=None),
        click.option("--init-model", default=None),
        click.option("--temperature", type=float, default=None),
    ]
    for d in reversed(decorators):
        f = d(f)
    return f


@click.group()
def main() -> None:
    """CovAgent — coverage-driven hardware verification orchestrator."""


@main.command()
@_common_options
@click.option(
    "--mock-llm/--real-llm",
    default=None,
    help="Use mock LLM (default: COVAGENT_MOCK_LLM env, falls back to mock).",
)
def run(
    env_file: Path | None,
    design: str | None,
    dashboard: Path | None,
    workspace: Path | None,
    mode: str | None,
    simulator: str | None,
    max_iterations: int | None,
    max_dispatches: int | None,
    goal_pct: float | None,
    orchestrator_model: str | None,
    agent_model: str | None,
    init_model: str | None,
    temperature: float | None,
    mock_llm: bool | None,
) -> None:
    """Run CovAgent end-to-end on a design from dashboard.json."""

    config = build_run_config(
        env_file=env_file,
        design=design, dashboard=dashboard, workspace=workspace,
        mode=mode, simulator=simulator,
        max_iterations=max_iterations, max_dispatches=max_dispatches,
        goal_pct=goal_pct,
        orchestrator_model=orchestrator_model, agent_model=agent_model,
        init_model=init_model, temperature=temperature,
    )

    use_mock = mock_llm if mock_llm is not None else use_mock_llm_default()
    if not use_mock and not get_openai_api_key():
        click.echo(
            "ERROR: --real-llm requested but OPENAI_API_KEY is not set "
            "(check .env or env vars).",
            err=True,
        )
        sys.exit(2)

    entry = get_design(config.dashboard_path, config.design_name)

    sim = get_adapter(config.simulator, sim_path=get_questa_path())

    run_id = make_run_id()
    run_paths = RunPaths.for_run(config.workspace, run_id, cov_ext=sim.extension())
    bootstrap_run(run_paths)
    run_paths.config_json.write_text(config.model_dump_json(indent=2))

    if config.simulator == "mock":
        run_paths.coverage_baseline.write_bytes(b"")

    llm = MockLLMProvider() if use_mock else OpenAILLMProvider(config)

    el = EventLogger(run_paths.events_jsonl, run_id=run_id)
    rl = RunLogRenderer(run_paths.run_log)
    tee = TeeLogger(el, rl)
    tee.emit(
        "run.started",
        {
            "config": json.loads(config.model_dump_json()),
            "workspace": str(config.workspace),
            "run_id": run_id,
            "llm_mode": "mock" if use_mock else "real",
        },
    )

    deps = RuntimeDeps(
        config=config,
        run_id=run_id,
        run_paths=run_paths,
        simulator=sim,
        llm=llm,
        tee=tee,
        design_root=entry.design_root,
        design_entry=entry,
    )

    initial_state = {
        "config": config,
        "run_id": run_id,
        "design_digest": None,
        "testplan": Testplan(mode=config.mode),
        "dispatch_log": [],
        "agents": {},
        "iteration": 0,
        "run_status": "init",
        "messages": [],
        "cycle": {
            "candidate_features": [],
            "in_flight": [],
            "pending_results": [],
            "coverage_snapshot": None,
        },
    }

    graph = build_orchestrator_graph(deps)
    t0 = time.monotonic()
    try:
        graph.invoke(initial_state, {"recursion_limit": 200})
    except Exception as exc:
        tee.emit(
            "error.raised",
            {"where": "main", "message": str(exc), "exception_type": type(exc).__name__},
        )
        click.echo(f"run errored: {exc}", err=True)
        tee.close()
        sys.exit(1)

    tee.close()
    click.echo(f"run {run_id} complete in {time.monotonic() - t0:.1f}s")
    click.echo(f"summary: {run_paths.summary_md}")


@main.command("show-config")
@_common_options
def show_config(
    env_file: Path | None,
    design: str | None,
    dashboard: Path | None,
    workspace: Path | None,
    mode: str | None,
    simulator: str | None,
    max_iterations: int | None,
    max_dispatches: int | None,
    goal_pct: float | None,
    orchestrator_model: str | None,
    agent_model: str | None,
    init_model: str | None,
    temperature: float | None,
) -> None:
    """Print the merged config (env + flags) without launching a run."""
    load_dotenv_file(env_file)
    try:
        config = build_run_config(
            env_file=env_file,
            design=design, dashboard=dashboard, workspace=workspace,
            mode=mode, simulator=simulator,
            max_iterations=max_iterations, max_dispatches=max_dispatches,
            goal_pct=goal_pct,
            orchestrator_model=orchestrator_model, agent_model=agent_model,
            init_model=init_model, temperature=temperature,
        )
    except ValueError as e:
        click.echo(f"config error: {e}", err=True)
        sys.exit(2)
    click.echo(config.model_dump_json(indent=2))
    click.echo("---")
    click.echo(f"OPENAI_API_KEY: {'set' if get_openai_api_key() else 'NOT SET'}")
    click.echo(f"OPENAI_BASE_URL: {get_openai_base_url() if get_openai_base_url() else 'http://api.openai.com/v1'}")
    qp = get_questa_path()
    click.echo(f"QUESTA_PATH: {qp if qp else f'(default {DEFAULT_SIM_PATH})'}")
    click.echo(f"MOCK_LLM: {use_mock_llm_default()}")


if __name__ == "__main__":
    main()
