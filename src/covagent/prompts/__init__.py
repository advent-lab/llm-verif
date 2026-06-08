"""Jinja prompt loader. Templates live alongside this module under prompts/*.j2."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_PROMPTS_DIR = Path(__file__).parent

_env = Environment(
    loader=FileSystemLoader(str(_PROMPTS_DIR)),
    undefined=StrictUndefined,
    keep_trailing_newline=True,
    autoescape=False,
)


def render(name: str, **vars: Any) -> str:
    """Render a prompt template by name (e.g. 'orchestrate' or 'agent_plan')."""
    template_name = name if name.endswith(".j2") else f"{name}.j2"
    template = _env.get_template(template_name)
    return template.render(**vars)


__all__ = ["render"]
