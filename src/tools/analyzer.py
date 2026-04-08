"""
Analyzer tool for the llm-verif multi-agent framework.
(See module docstring in original file for full architecture notes.)
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

from langchain.tools import tool

# ── Module-level state ─────────────────────────────────────────────────────────

_config = None
_last_coverage_result: Optional[Dict[str, Any]] = None


def set_config(config) -> None:
    global _config
    _config = config


def set_last_coverage_result(result: Dict[str, Any]) -> None:
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
    Read design and context files, truncating each to max_chars_per_file.

    max_chars_per_file is computed adaptively by the caller based on the
    total number of files so that the combined RTL section stays within a
    reasonable token budget regardless of design complexity.
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


def _adaptive_max_chars(num_files: int, total_budget: int = 20000) -> int:
    """
    Compute per-file character budget so total RTL context stays within
    total_budget chars regardless of how many files the design has.

    Examples (total_budget=20000):
      1 file  → 6000  (capped at 6000)
      3 files → 6000  (capped at 6000)
      6 files → 3333
     12 files → 1666
    """
    if num_files <= 0:
        return 6000
    per_file = total_budget // num_files
    return max(500, min(6000, per_file))


def _build_uncovered_items(
    coverage_result: Dict[str, Any],
    max_items: int,
) -> List[Dict[str, Any]]:
    """Convert last coverage result into the uniform list-of-dicts for the prompt."""
    items: List[Dict[str, Any]] = []
    phase = coverage_result.get("phase", "code")

    if phase == "functional":
        cg_pct_map: Dict[str, float] = {}
        for cg in coverage_result.get("covergroups", []):
            cg_pct_map[cg["name"]] = cg.get("coverage", 0.0)

        raw_bins = coverage_result.get("uncovered_bins", [])
        enriched = [
            {
                "covergroup":   entry.get("covergroup", "unknown"),
                "bin":          entry.get("bin_name", entry.get("bin", "unknown")),
                "coverpoint":   entry.get("coverpoint", entry.get("bin_name", "unknown")),
                "coverage_pct": cg_pct_map.get(entry.get("covergroup", ""), 0.0),
            }
            for entry in raw_bins
        ]
        enriched.sort(key=lambda x: (x["coverage_pct"], x["covergroup"]))
        items = enriched[:max_items]

    else:
        uncovered_lines: Dict[str, List[int]] = coverage_result.get("uncovered_lines", {})
        for file_path, line_nums in sorted(uncovered_lines.items()):
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


def _estimate_prompt_chars(
    system_prompt: str,
    human_message: str,
) -> int:
    """Rough character count of the full prompt (1 token ≈ 4 chars)."""
    return len(system_prompt) + len(human_message)


def _make_analyzer_call(
    analyzer_llm,
    system_prompt: str,
    human_message: str,
    coverage_phase: str,
    uncovered_items: List[Dict],
) -> Dict[str, Any]:
    """Single LLM call to the analyzer. Returns the standard result dict."""
    from langchain_core.messages import SystemMessage, HumanMessage

    char_estimate = _estimate_prompt_chars(system_prompt, human_message)
    logging.info(
        f"invoke_analyzer: calling analyzer LLM "
        f"(phase={coverage_phase}, items={len(uncovered_items)}, "
        f"~{char_estimate // 4} prompt tokens)"
    )

    response = analyzer_llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_message),
    ])

    recommendation = (
        response.content if hasattr(response, "content") else str(response)
    )
    return recommendation


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
    you do not need to pass the uncovered bins yourself.

    Args:
        hint:                Optional plain-text context to pass to the analyzer.
        max_uncovered_items: Maximum number of uncovered items to send.  Default: 20.

    Returns:
        success (bool), recommendation (str), uncovered_item_count (int),
        coverage_phase (str), error (str)
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
        return {
            "success": True,
            "recommendation": (
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
            ),
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

        # ── FIX 1: Adaptive per-file character budget ──────────────────────
        # Scale down per-file RTL budget based on total file count so the
        # combined RTL section stays within ~20 000 chars regardless of how
        # many context files the design has.  The TRNG design has 12 files;
        # with the old fixed 6000-char limit that produced ~72 000 RTL chars
        # and caused the model to return empty responses.
        num_files     = len(design_files) + len(context_files)
        max_chars     = _adaptive_max_chars(num_files)
        logging.info(
            f"invoke_analyzer: {num_files} RTL file(s), "
            f"per-file budget = {max_chars} chars"
        )

        rtl_snippets = _load_rtl_snippets(design_files, context_files, max_chars)

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
    coverage_phase  = "code"
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

    # ── Make analyzer LLM call with empty-response retry ──────────────────
    try:
        from langchain_openai import ChatOpenAI

        analyzer_llm = ChatOpenAI(
            model=model,
            temperature=0,
            max_tokens=2000,
            api_key=api_key,
        )

        human_message = (
            "Analyse the uncovered coverage items listed in the system prompt "
            "and produce your structured recommendation now."
        )
        if hint:
            human_message += f"\n\nAdditional context from the orchestrator:\n{hint}"

        recommendation = _make_analyzer_call(
            analyzer_llm, system_prompt, human_message,
            coverage_phase, uncovered_items,
        )

        # ── FIX 2: Empty-response guard ────────────────────────────────────
        # gpt-5.2 (and some other models) occasionally return an empty string
        # when the prompt is very large.  If this happens, retry once with a
        # reduced item count (half) and tighter RTL budget (half again) before
        # giving up.  This handles large designs like TRNG (12 context files)
        # where the original 20-item / 6000-char-per-file prompt was too large.
        if not recommendation.strip():
            retry_items = max(5, len(uncovered_items) // 2)
            retry_chars = max(300, max_chars // 2)

            logging.warning(
                f"invoke_analyzer: received empty recommendation "
                f"(~{_estimate_prompt_chars(system_prompt, human_message) // 4} tokens). "
                f"Retrying with {retry_items} items and {retry_chars} chars/file."
            )

            # Rebuild RTL snippets and items with tighter budgets
            rtl_snippets_retry = _load_rtl_snippets(
                design_files, context_files, retry_chars
            )
            uncovered_items_retry = (
                _build_uncovered_items(_last_coverage_result, retry_items)
                if _last_coverage_result is not None
                else []
            )
            system_prompt_retry = build_analyzer_prompt(
                design_name=design_name,
                uncovered_items=uncovered_items_retry,
                rtl_snippets=rtl_snippets_retry,
                previous_attempts=hint if hint else None,
                coverage_phase=coverage_phase,
            )

            recommendation = _make_analyzer_call(
                analyzer_llm, system_prompt_retry, human_message,
                coverage_phase, uncovered_items_retry,
            )
            uncovered_items = uncovered_items_retry  # update count for return value

            if not recommendation.strip():
                logging.error(
                    "invoke_analyzer: empty recommendation after retry — "
                    "model may be refusing the prompt. Returning empty."
                )
                return {
                    "success": False,
                    "recommendation": "",
                    "uncovered_item_count": len(uncovered_items),
                    "coverage_phase": coverage_phase,
                    "error": (
                        "Analyzer LLM returned empty response after retry. "
                        "Prompt may be too large for this model."
                    ),
                }

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
