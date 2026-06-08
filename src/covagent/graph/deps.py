"""Runtime dependencies passed into graph nodes via closure.

Nodes are pure functions of (state, deps) — `deps` carries the simulator,
LLM provider, paths, and logging hooks. Tests inject a `MockLLMProvider`
and `MockAdapter`; production wires `OpenAILLMProvider` + `QuestaAdapter`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from langchain_core.language_models import BaseChatModel

from covagent.config import RunConfig
from covagent.logging.run_log import TeeLogger
from covagent.simulators.base import SimulatorAdapter
from covagent.workspace.dashboard import DesignEntry
from covagent.workspace.layout import RunPaths


class LLMProvider(Protocol):
    """Returns a chat model for a given role. Roles map to RunConfig.models."""

    def get(self, role: Literal["init", "orchestrate", "agent"]) -> BaseChatModel: ...


@dataclass
class RuntimeDeps:
    config: RunConfig
    run_id: str
    run_paths: RunPaths
    simulator: SimulatorAdapter
    llm: LLMProvider
    tee: TeeLogger
    # Single sandbox root for all design reads. Every file the agent can read
    # (RTL, spec, context) lives under this directory by dashboard convention:
    # `<workspace>/data/<design_name>/<category>/<file>`.
    design_root: Path | None = None
    # Resolved dashboard entry — categorized file lists for prompt rendering
    # (design / design_context / spec / etc.). Not used for sandboxing.
    design_entry: DesignEntry | None = None
