"""Settings loader — `.env` + CLI overrides → `RunConfig`.

Knobs are read from environment variables prefixed with `COVAGENT_`.
A `.env` file at the working directory (or one passed via `env_file`) is
loaded into `os.environ` before any reads, so a single file can drive a run.

CLI flags override env vars; env vars override the defaults baked into
`covagent.config.RunConfig`. Secrets that aren't framework-specific
(`OPENAI_API_KEY`) are read by the underlying SDK and don't need a
`COVAGENT_` prefix — `python-dotenv` still loads them.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from covagent.config import Budget, CoverageGoal, ModelConfig, RunConfig

_PREFIX = "COVAGENT_"


def _env(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(_PREFIX + name)
    return val if val not in (None, "") else default


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    return int(raw) if raw is not None else default


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    return float(raw) if raw is not None else default


def load_dotenv_file(env_file: Path | None = None) -> None:
    """Load `.env` into `os.environ`. Idempotent; existing env vars win."""
    if env_file is not None:
        load_dotenv(env_file, override=False)
    else:
        load_dotenv(override=False)


def build_run_config(
    *,
    env_file: Path | None = None,
    design: str | None = None,
    dashboard: Path | None = None,
    workspace: Path | None = None,
    mode: str | None = None,
    simulator: str | None = None,
    max_iterations: int | None = None,
    max_dispatches: int | None = None,
    max_wall_time_s: int | None = None,
    per_dispatch_attempts: int | None = None,
    goal_pct: float | None = None,
    per_scope_pct: float | None = None,
    orchestrator_model: str | None = None,
    agent_model: str | None = None,
    init_model: str | None = None,
    temperature: float | None = None,
) -> RunConfig:
    """Build a frozen `RunConfig` from `.env` + caller-supplied overrides.

    Each keyword is `None` by default; a non-`None` value wins over the
    matching env var. Required fields raise `ValueError` if neither source
    supplies them.
    """
    load_dotenv_file(env_file)

    design_name = design or _env("DESIGN")
    if not design_name:
        raise ValueError(
            "design name not set — pass --design or set COVAGENT_DESIGN in .env"
        )

    dashboard_path = dashboard or Path(_env("DASHBOARD") or "work/dashboard.json")
    workspace_path = workspace or Path(_env("WORKSPACE") or "work/workspaces/default")
    mode_v = mode or _env("MODE") or "functional"
    simulator_v = simulator or _env("SIMULATOR") or "questa"

    goal = CoverageGoal(
        overall_pct=goal_pct if goal_pct is not None else _env_float("GOAL_PCT", 90.0),
        per_scope_pct=(
            per_scope_pct
            if per_scope_pct is not None
            else (float(_env("GOAL_PER_SCOPE_PCT")) if _env("GOAL_PER_SCOPE_PCT") else None)
        ),
    )
    budget = Budget(
        max_iterations=max_iterations if max_iterations is not None else _env_int("MAX_ITERATIONS", 20),
        max_dispatches=max_dispatches if max_dispatches is not None else _env_int("MAX_DISPATCHES", 100),
        max_wall_time_s=max_wall_time_s if max_wall_time_s is not None else _env_int("MAX_WALL_TIME_S", 24 * 3600),
        per_dispatch_attempts=per_dispatch_attempts if per_dispatch_attempts is not None else _env_int("PER_DISPATCH_ATTEMPTS", 5),
    )
    models = ModelConfig(
        orchestrator=orchestrator_model or _env("ORCHESTRATOR_MODEL"),
        agent=agent_model or _env("AGENT_MODEL"),
        init=init_model or _env("INIT_MODEL"),
        temperature=temperature if temperature is not None else _env_float("TEMPERATURE", 0.0),
    )

    return RunConfig(
        workspace=workspace_path,
        design_name=design_name,
        dashboard_path=dashboard_path,
        mode=mode_v,  # type: ignore[arg-type]
        simulator=simulator_v,  # type: ignore[arg-type]
        goal=goal,
        budget=budget,
        models=models,
    )


def get_openai_api_key() -> str | None:
    """Return `OPENAI_API_KEY` from env (loaded via `.env`)."""
    return os.environ.get("OPENAI_API_KEY")

def get_openai_base_url() -> str | None:
    """Return `OPENAI_BASE_URL` from env (loaded via `.env`)."""
    return os.environ.get("OPENAI_BASE_URL")


def get_questa_path() -> Path | None:
    """Return Questa install dir from `COVAGENT_QUESTA_PATH` (or `QUESTA_PATH`)."""
    raw = os.environ.get("COVAGENT_QUESTA_PATH") or os.environ.get("QUESTA_PATH")
    return Path(raw) if raw else None


def use_mock_llm_default() -> bool:
    """Default for `--mock-llm/--real-llm` from env (`COVAGENT_MOCK_LLM=1`)."""
    raw = _env("MOCK_LLM")
    if raw is None:
        return True
    return raw.strip().lower() in ("1", "true", "yes", "on")
