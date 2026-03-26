"""
Analyzer tool for the llm-verif multi-agent framework.

This module implements the ``invoke_analyzer`` tool which the orchestrator
(agent_node) calls when it needs targeted guidance on how to hit specific
uncovered coverage bins or lines.

Architecture
------------
The analyzer is a *specialist* agent with a narrow, focused context:

    Orchestrator (agent_node)
         |
         |  calls invoke_analyzer(hint)
         v
    invoke_analyzer tool  ←── this file
         |
         |  reads _last_coverage_result (set by update_state_node)
         |  builds focused prompt via build_analyzer_prompt()
         |  makes a single LLM call (no tool loop)
         v
    Analyzer LLM response
         |
         |  returns structured recommendation string
         v
    Orchestrator receives recommendation as a ToolMessage.
    update_state_node stores it in state["analyzer_recommendation"]
    and increments state["analyzer_calls"].
    Orchestrator uses the recommendation when generating the next
    testbench iteration.

The analyzer does NOT compile, simulate, or parse coverage — it only reasons
about RTL and produces a recommendation.  Keeping it tool-free means a single
LLM call is sufficient and the context window stays small.

Coverage result handoff
-----------------------
Because LangGraph tools cannot directly read agent state, the last coverage
parse result is handed off via a module-level variable.  update_state_node
in react.py calls set_last_coverage_result() immediately after processing a
successful parse_coverage or parse_functional_coverage tool message.  The
invoke_analyzer tool reads this variable when building its prompt so it always
has the most recent structured uncovered data without needing the orchestrator
to manually serialize it into the hint string.

Stub mode
---------
When ANALYZER_STUB=1 is set in the environment, invoke_analyzer returns a
hardcoded stub recommendation instead of making a real LLM call.  This allows
the graph wiring and state flow to be tested end-to-end before the full
prompt engineering is finalised.

Configuration
-------------
Like the simulation and analysis tools, the analyzer reads its config via
``set_config(config)``, which must be called from ``set_tool_config`` in
``src/tools/__init__.py`` before the graph runs.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

from langchain.tools import tool

# ── Module-level state ─────────────────────────────────────────────────────────

# Config reference — populated by set_config() before the graph runs.
_config = None

# Last coverage parse result — set by update_state_node in react.py immediately
# after a successful parse_coverage or parse_functional_coverage call.
# Shape mirrors the tool return values from analysis.py:
#   {
#       "phase":            "functional" | "code",
#       "covergroups":      [...],          # functional only
#       "uncovered_bins":   [...],          # functional only — flat list
#       "uncovered_lines":  {...},          # code only — {file: [line_nums]}
#       "coverage_pct":     float,
#   }
_last_coverage_result: Optional[Dict[str, Any]] = None


def set_config(config) -> None:
    """Register the shared config object with the analyzer tool."""
    global _config
    _config = config


def set_last_coverage_result(result: Dict[str, Any]) -> None:
    """
    Store the most recent coverage parse result so invoke_analyzer can read it.

    Called by update_state_node in react.py after every successful
    parse_coverage or parse_functional_coverage tool message.

    Args:
        result: Dict with keys:
            phase (str):           "functional" or "code"
            covergroups (list):    Covergroup dicts from parse_functional_coverage
                                   (empty list for code coverage phase)
            uncovered_bins (list): Flat uncovered bin dicts from
                                   parse_functional_coverage (empty for code phase)
            uncovered_lines (dict): {file_path: [line_nums]} from parse_coverage
                                    (empty dict for functional phase)
            coverage_pct (float):  Final cumulative coverage percentage
    """
    global _last_coverage_result
    _last_coverage_result = result
    logging.debug(
        f"analyzer: last_coverage_result updated "
        f"(phase={result.get('phase')}, "
        f"coverage={result.get('coverage_pct', 0.0):.1f}%)"
    )


# ── Internal helpers ───────────────────────────────────────────────────────────

def _load_rtl_snippets(
    design_files: List[str],
    context_files: List[str],
    max_chars_per_file: int = 6000,
) -> Dict[str, str]:
    """
    Read the design and context files and return a dict mapping each file path
    to its source text (truncated to ``max_chars_per_file`` characters).

    Files that cannot be read are silently skipped with a warning log so that
    a missing file never prevents the analyzer from running.

    Args:
        design_files:       Paths to the primary DUT files.
        context_files:      Paths to supporting/submodule files.
        max_chars_per_file: Maximum number of characters to include per file.
                            Keeps the analyzer context window manageable.

    Returns:
        Dict mapping absolute path string → source text string.
    """
    snippets: Dict[str, str] = {}
    all_files = list(design_files) + list(context_files)

    for file_path in all_files:
        try:
            text = Path(file_path).read_text(encoding="utf-8", errors="ignore")
            if len(text) > max_chars_per_file:
                text = (
                    text[:max_chars_per_file]
                    + f"\n... [truncated at {max_chars_per_file} chars]"
                )
            snippets[file_path] = text
        except OSError as e:
            logging.warning(f"invoke_analyzer: could not read {file_path}: {e}")

    return snippets


def _build_uncovered_items(
    coverage_result: Dict[str, Any],
    max_items: int,
) -> List[Dict[str, Any]]:
    """
    Convert the last coverage result into the uniform list-of-dicts format
    expected by ``build_analyzer_prompt``.

    For functional coverage we combine data from both ``covergroups`` (which
    carries per-covergroup coverage percentages) and ``uncovered_bins`` (which
    is a flat list).  The covergroups list is the authoritative source for
    coverage percentages; uncovered_bins is used to drive the item list.

    For code coverage we convert {file: [line_nums]} into the list-of-dicts
    shape and attempt to read the actual source line text so the analyzer has
    concrete code to reason about.

    Items are sorted so the lowest-coverage covergroups / earliest uncovered
    lines come first.  The list is capped at ``max_items`` entries.

    Args:
        coverage_result: Dict from _last_coverage_result (see set_last_coverage_result)
        max_items:       Maximum number of items to return.

    Returns:
        List of normalised dicts suitable for build_analyzer_prompt().
    """
    items: List[Dict[str, Any]] = []
    phase = coverage_result.get("phase", "code")

    if phase == "functional":
        # Build a lookup from covergroup name → coverage_pct using the
        # richer covergroups list (which has per-CG coverage percentages).
        cg_pct_map: Dict[str, float] = {}
        for cg in coverage_result.get("covergroups", []):
            cg_pct_map[cg["name"]] = cg.get("coverage", 0.0)

        # Build items from the flat uncovered_bins list, enriched with pct.
        # Sort by coverage ascending so lowest-coverage groups come first.
        raw_bins = coverage_result.get("uncovered_bins", [])
        enriched = [
            {
                "covergroup":   entry.get("covergroup", "unknown"),
                # bin_name is the key used by analysis.py's flat list
                "bin":          entry.get("bin_name", entry.get("bin", "unknown")),
                # coverpoint key is absent in the flat list; use bin_name as
                # a reasonable fallback so the prompt always gets a value
                "coverpoint":   entry.get("coverpoint", entry.get("bin_name", "unknown")),
                "coverage_pct": cg_pct_map.get(entry.get("covergroup", ""), 0.0),
            }
            for entry in raw_bins
        ]
        # Sort: lowest coverage first, then alphabetically by covergroup name
        enriched.sort(key=lambda x: (x["coverage_pct"], x["covergroup"]))
        items = enriched[:max_items]

    else:
        # Code coverage — {file_path: [line_nums]}
        uncovered_lines: Dict[str, List[int]] = coverage_result.get("uncovered_lines", {})

        for file_path, line_nums in sorted(uncovered_lines.items()):
            # Attempt to read source lines for this file once
            try:
                source_lines = (
                    Path(file_path)
                    .read_text(encoding="utf-8", errors="ignore")
                    .splitlines()
                )
            except OSError:
                source_lines = []

            for ln in sorted(line_nums):
                if source_lines and 1 <= ln <= len(source_lines):
                    src_text = source_lines[ln - 1].strip()
                else:
                    src_text = "(source unavailable)"

                items.append({
                    "file":        file_path,
                    "line_number": ln,
                    "source_text": src_text,
                })

                if len(items) >= max_items:
                    break

            if len(items) >= max_items:
                break

    return items


# ── Tool ───────────────────────────────────────────────────────────────────────

@tool
def invoke_analyzer(
    hint: str = "",
    max_uncovered_items: int = 20,
) -> Dict[str, Any]:
    """
    Invoke the analyzer agent to get targeted stimulus recommendations for
    uncovered coverage bins or lines.

    Call this tool when:
    - Coverage has plateaued for one or more iterations with no improvement
    - You are unsure why specific bins or lines are not being hit
    - You want a targeted analysis before generating the next testbench

    The analyzer reads the most recent coverage parse result automatically —
    you do not need to pass the uncovered bins yourself.  It examines them
    alongside the RTL source and returns a structured recommendation explaining
    why each item is uncovered and what stimulus sequence would hit it.

    Use the recommendation returned in the 'recommendation' field to guide
    your next testbench iteration.  The framework also stores it in
    state['analyzer_recommendation'] so you can refer back to it.

    Args:
        hint:                Optional plain-text context to pass to the
                             analyzer, e.g. "we have tried toggling cs for
                             50 cycles but busy_digest_hold is still zero".
                             The more specific the hint, the better the
                             recommendation.  Leave empty if no additional
                             context is available.
        max_uncovered_items: Maximum number of uncovered items to send to the
                             analyzer in one call.  Items beyond this limit are
                             dropped (lowest-coverage items are prioritised).
                             Keeping this small prevents the analyzer context
                             from growing too large.  Default: 20.

    Returns:
        Dictionary with:
            success (bool):             True if the analyzer produced a recommendation.
            recommendation (str):       The analyzer's structured recommendation text.
                                        Empty string if success is False.
            uncovered_item_count (int): Number of items that were analysed.
            coverage_phase (str):       "functional" or "code" — which phase was analysed.
            error (str):                Error message if success is False.
    """
    if _config is None:
        return {
            "success": False,
            "recommendation": "",
            "uncovered_item_count": 0,
            "coverage_phase": "unknown",
            "error": "Analyzer not configured — set_config() was not called.",
        }

    # ── Stub mode ──────────────────────────────────────────────────────────
    stub_mode = os.getenv("ANALYZER_STUB", "0") == "1"
    if stub_mode:
        logging.info("invoke_analyzer: running in STUB mode (ANALYZER_STUB=1)")
        stub_recommendation = (
            "[STUB RECOMMENDATION]\n\n"
            "ROOT CAUSE\n"
            "This is a stub response used for testing graph wiring. "
            "No real RTL analysis was performed.\n\n"
            "STIMULUS STRATEGY\n"
            "1. Write 0x1 to the CTRL register to trigger init.\n"
            "2. Wait for ready to assert.\n"
            "3. Write 0x2 to trigger next.\n\n"
            "PRIORITY ORDER\n"
            "1. All items — stub mode, no priority analysis.\n\n"
            "WAIVE CANDIDATES\n"
            "None identified in stub mode."
        )
        return {
            "success": True,
            "recommendation": stub_recommendation,
            "uncovered_item_count": 0,
            "coverage_phase": "unknown",
            "error": "",
        }

    # ── Gather static context from config ──────────────────────────────────
    try:
        design_files  = [str(f) for f in _config.design_files]
        context_files = [str(f) for f in _config.design_context_files]
        design_name   = _config.design_name
        model         = _config.model
        api_key       = _config.openai_api_key

        rtl_snippets = _load_rtl_snippets(design_files, context_files)

    except Exception as e:
        logging.error(f"invoke_analyzer: failed to gather static context: {e}")
        return {
            "success": False,
            "recommendation": "",
            "uncovered_item_count": 0,
            "coverage_phase": "unknown",
            "error": f"Failed to gather context: {e}",
        }

    # ── Extract uncovered items from last coverage result ──────────────────
    coverage_phase = "code"
    uncovered_items: List[Dict[str, Any]] = []

    if _last_coverage_result is not None:
        coverage_phase = _last_coverage_result.get("phase", "code")
        try:
            uncovered_items = _build_uncovered_items(
                _last_coverage_result, max_uncovered_items
            )
            logging.info(
                f"invoke_analyzer: extracted {len(uncovered_items)} uncovered items "
                f"from last {coverage_phase} coverage result"
            )
        except Exception as e:
            # Non-fatal — we can still run with an empty list and rely on hint
            logging.warning(
                f"invoke_analyzer: failed to extract uncovered items "
                f"(will rely on hint): {e}"
            )
    else:
        logging.warning(
            "invoke_analyzer: no coverage result available — "
            "orchestrator should call parse_coverage or parse_functional_coverage first"
        )

    # ── Build analyzer prompt ──────────────────────────────────────────────
    try:
        from ..prompts.analyzer_prompt import build_analyzer_prompt

        system_prompt = build_analyzer_prompt(
            design_name=design_name,
            uncovered_items=uncovered_items,
            rtl_snippets=rtl_snippets,
            previous_attempts=hint if hint else None,
            coverage_phase=coverage_phase,
        )
    except Exception as e:
        logging.error(f"invoke_analyzer: failed to build prompt: {e}")
        return {
            "success": False,
            "recommendation": "",
            "uncovered_item_count": 0,
            "coverage_phase": coverage_phase,
            "error": f"Failed to build analyzer prompt: {e}",
        }

    # ── Make analyzer LLM call ─────────────────────────────────────────────
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        # Use the same model as the orchestrator by default.
        # In a future session this can be overridden via a dedicated config
        # field (e.g. config.analyzer_model) to use a stronger reasoning model.
        analyzer_llm = ChatOpenAI(
            model=model,
            temperature=0,    # Deterministic — analysis should be consistent
            max_tokens=2000,  # Enough for a thorough structured recommendation
            api_key=api_key,
        )

        human_message = (
            "Analyse the uncovered coverage items listed in the system prompt "
            "and produce your structured recommendation now."
        )
        if hint:
            human_message += f"\n\nAdditional context from the orchestrator:\n{hint}"

        logging.info(
            f"invoke_analyzer: calling analyzer LLM "
            f"(model={model}, phase={coverage_phase}, items={len(uncovered_items)})"
        )

        response = analyzer_llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_message),
        ])

        recommendation = (
            response.content if hasattr(response, "content") else str(response)
        )

        logging.info(
            f"invoke_analyzer: received recommendation ({len(recommendation)} chars)"
        )

        return {
            "success": True,
            "recommendation": recommendation,
            "uncovered_item_count": len(uncovered_items),
            "coverage_phase": coverage_phase,
            "error": "",
        }

    except Exception as e:
        logging.error(f"invoke_analyzer: LLM call failed: {e}")
        return {
            "success": False,
            "recommendation": "",
            "uncovered_item_count": 0,
            "coverage_phase": coverage_phase,
            "error": f"Analyzer LLM call failed: {e}",
        }
