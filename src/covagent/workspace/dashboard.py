"""dashboard.json loader — design name → resolved RTL/spec/context paths.

Adapted from legacy_src/utils/dashboard_loader.py: same $(BASE_DIR)
substitution, same accept-string-or-list normalization, but the output
shape is a Pydantic model that fits the new framework.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class DesignEntry(BaseModel):
    name: str
    design_root: Path
    design: list[Path] = Field(default_factory=list)
    design_context: list[Path] = Field(default_factory=list)
    spec: list[Path] = Field(default_factory=list)
    spec_context: list[Path] = Field(default_factory=list)
    verif: list[Path] = Field(default_factory=list)
    verif_context: list[Path] = Field(default_factory=list)
    makefile: list[Path] = Field(default_factory=list)
    compile_deps: list[Path] = Field(default_factory=list)


_FIELDS = (
    "design",
    "design_context",
    "spec",
    "spec_context",
    "verif",
    "verif_context",
    "makefile",
    "compile_deps",
)


def _normalize_list(raw: object) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(x) for x in raw]
    raise ValueError(f"unexpected dashboard field type: {type(raw).__name__}")


def _resolve(template: str, variables: dict[str, str]) -> str:
    out = template
    for k, v in variables.items():
        out = out.replace(f"$({k})", v)
    return out


def _resolve_list(raws: list[str], variables: dict[str, str]) -> list[Path]:
    return [Path(_resolve(r, variables)).resolve() for r in raws]


def load_dashboard(
    dashboard_path: Path, base_dir: Path | None = None
) -> dict[str, DesignEntry]:
    dashboard_path = Path(dashboard_path).resolve()
    if not dashboard_path.exists():
        raise FileNotFoundError(f"Dashboard not found: {dashboard_path}")
    raw = json.loads(dashboard_path.read_text())
    base = (base_dir or dashboard_path.parent / "data").resolve()
    out: dict[str, DesignEntry] = {}
    for name, entry in raw.items():
        variables = {"BASE_DIR": str(base), "DESIGN_NAME": name}
        kwargs: dict[str, object] = {
            "name": name,
            "design_root": (base / name).resolve(),
        }
        for f in _FIELDS:
            kwargs[f] = _resolve_list(_normalize_list(entry.get(f)), variables)
        out[name] = DesignEntry(**kwargs)
    return out


def get_design(
    dashboard_path: Path, name: str, base_dir: Path | None = None
) -> DesignEntry:
    designs = load_dashboard(dashboard_path, base_dir)
    if name not in designs:
        raise KeyError(
            f"Design '{name}' not in dashboard. Available: {sorted(designs)[:5]}..."
        )
    return designs[name]
