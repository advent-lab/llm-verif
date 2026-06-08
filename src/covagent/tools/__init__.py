"""Tool registration — LangChain StructuredTool factories per tool module.

Each `make_*_tools(ctx)` returns a list of `StructuredTool` objects ready
to be bound to an LLM. The factory captures `ctx` in closure and routes
every invocation through `_wrap.call_with_events` so events.jsonl gets
`tool.called` / `tool.returned` for free.
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from covagent.tools import agents as _agents
from covagent.tools import coverage as _coverage
from covagent.tools import filesystem as _fs
from covagent.tools import rtl_spec as _rtl_spec
from covagent.tools import simulation as _sim
from covagent.tools import testplan as _tp
from covagent.tools._wrap import call_with_events
from covagent.tools.types import ToolContext, ToolResult


class _ReadFileArgs(BaseModel):
    path: str
    max_bytes: int | None = None


class _WriteFileArgs(BaseModel):
    path: str
    content: str


class _EditFileArgs(BaseModel):
    path: str
    old_string: str
    new_string: str
    replace_all: bool = False


class _ReadRtlArgs(BaseModel):
    path: str
    line_start: int | None = None
    line_end: int | None = None


class _ReadSpecArgs(BaseModel):
    query: str
    section: str | None = None
    max_chars: int = 4000


class _ReadSimLogArgs(BaseModel):
    path: str
    tail_lines: int = 200


class _QueryCoverageArgs(BaseModel):
    scope: str = "*"
    mode: str | None = None


class _RunSimArgs(BaseModel):
    testbench_name: str
    sources: list[str] | None = None
    timeout_s: int = 600
    num_runs: int = 1


class _ReadTestplanArgs(BaseModel):
    target_type: str | None = Field(default=None, description="testpoint|covergroup|code_scope")
    name: str | None = None
    status: str | None = None


class _NoArgs(BaseModel):
    pass


class _ReadHistoryArgs(BaseModel):
    target_type: str
    name: str


class _ReadDispatchLogArgs(BaseModel):
    last_n: int = 20


class _PatchTestplanArgs(BaseModel):
    target_type: str
    name: str
    fields: dict


class _AppendHistoryArgs(BaseModel):
    target_type: str
    name: str
    outcome: str
    summary: str
    artifacts_path: str | None = None
    agent_id: str | None = None


class _BuildTestplanArgs(BaseModel):
    plan: dict


class _ReadAgentsArgs(BaseModel):
    status: str | None = None
    feature: str | None = None


def _bind(ctx: ToolContext, name: str, fn, args_schema: type[BaseModel], description: str) -> StructuredTool:
    def _runner(**kwargs) -> ToolResult:
        return call_with_events(ctx, name, lambda **kw: fn(ctx, **kw), kwargs)

    return StructuredTool.from_function(
        _runner,
        name=name,
        description=description,
        args_schema=args_schema,
    )


def make_filesystem_tools(ctx: ToolContext) -> list[StructuredTool]:
    return [
        _bind(ctx, "read_file", _fs.read_file, _ReadFileArgs,
              "Read a file from your work_dir."),
        _bind(ctx, "write_file", _fs.write_file, _WriteFileArgs,
              "Create or fully overwrite a file in your work_dir."),
        _bind(ctx, "edit_file", _fs.edit_file, _EditFileArgs,
              "Apply a surgical patch to a file: replace old_string with new_string. "
              "old_string must match exactly once, unless replace_all=true."),
    ]


def make_rtl_spec_tools(ctx: ToolContext) -> list[StructuredTool]:
    return [
        _bind(ctx, "read_rtl", _rtl_spec.read_rtl, _ReadRtlArgs,
              "Read RTL source. Optional line_start/line_end to keep context small."),
        _bind(ctx, "read_spec_excerpt", _rtl_spec.read_spec_excerpt, _ReadSpecArgs,
              "Search the spec docs for a query string; returns matching paragraphs."),
        _bind(ctx, "read_sim_log", _rtl_spec.read_sim_log, _ReadSimLogArgs,
              "Read the tail of a sim log inside your work_dir."),
    ]


def make_coverage_tools(ctx: ToolContext) -> list[StructuredTool]:
    return [
        _bind(ctx, "query_coverage", _coverage.query_coverage, _QueryCoverageArgs,
              "Query the master coverage DB. Returns structured numbers (never parse report text)."),
    ]


def make_simulation_tools(ctx: ToolContext) -> list[StructuredTool]:
    return [
        _bind(ctx, "run_sim", _sim.run_sim, _RunSimArgs,
              "Compile and simulate a testbench. Returns paths to log + per-dispatch coverage delta."),
    ]


def make_testplan_read_tools(ctx: ToolContext) -> list[StructuredTool]:
    return [
        _bind(ctx, "read_testplan", _tp.read_testplan, _ReadTestplanArgs,
              "Read the testplan: full plan, a filtered list, or a single named item."),
        _bind(ctx, "read_summary", _tp.read_summary, _NoArgs,
              "Counts and percentages — for 'are we done' checks."),
        _bind(ctx, "read_history", _tp.read_history, _ReadHistoryArgs,
              "Read one item's history without paying the full plan cost."),
        _bind(ctx, "read_dispatch_log", _tp.read_dispatch_log, _ReadDispatchLogArgs,
              "Recent orchestrator dispatches."),
    ]


def make_testplan_write_tools(ctx: ToolContext) -> list[StructuredTool]:
    return [
        _bind(ctx, "patch_testplan", _tp.patch_testplan, _PatchTestplanArgs,
              "Merge fields into one item. History cannot be patched here."),
        _bind(ctx, "append_history", _tp.append_history, _AppendHistoryArgs,
              "Append a structured outcome to an item's history."),
    ]


def make_build_testplan_tools(ctx: ToolContext) -> list[StructuredTool]:
    return [
        _bind(ctx, "build_testplan", _tp.build_testplan, _BuildTestplanArgs,
              "INIT-only: install the freshly-constructed testplan."),
    ]


def make_agents_tools(ctx: ToolContext) -> list[StructuredTool]:
    return [
        _bind(ctx, "read_agents", _agents.read_agents, _ReadAgentsArgs,
              "Roster view: list AgentMetadata entries, optionally filtered by status or feature."),
    ]


def tools_for_init(ctx: ToolContext) -> list[StructuredTool]:
    return (
        make_rtl_spec_tools(ctx)[:2]
        + make_coverage_tools(ctx)
        + make_build_testplan_tools(ctx)
    )


def tools_for_orchestrate(ctx: ToolContext) -> list[StructuredTool]:
    return (
        make_testplan_read_tools(ctx)
        + make_testplan_write_tools(ctx)
        + make_agents_tools(ctx)
        + make_coverage_tools(ctx)
        + make_rtl_spec_tools(ctx)[:2]
    )


def tools_for_agent_plan(ctx: ToolContext) -> list[StructuredTool]:
    return (
        make_rtl_spec_tools(ctx)[:2]
        + make_coverage_tools(ctx)
    )


def tools_for_agent_act(ctx: ToolContext) -> list[StructuredTool]:
    return (
        make_rtl_spec_tools(ctx)[:1]
        + make_filesystem_tools(ctx)[1:]
        + make_simulation_tools(ctx)
        + make_rtl_spec_tools(ctx)[2:]
    )


__all__ = [
    "ToolContext",
    "ToolResult",
    "make_filesystem_tools",
    "make_rtl_spec_tools",
    "make_coverage_tools",
    "make_simulation_tools",
    "make_testplan_read_tools",
    "make_testplan_write_tools",
    "make_build_testplan_tools",
    "make_agents_tools",
    "tools_for_init",
    "tools_for_orchestrate",
    "tools_for_agent_plan",
    "tools_for_agent_act",
]
