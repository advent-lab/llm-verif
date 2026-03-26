"""
Prompt builder for the analyzer agent.

The analyzer is a specialist agent invoked by the orchestrator (agent_node)
when it needs deep reasoning about *why* specific coverage bins or lines are
uncovered and *what stimulus* would hit them.

Unlike the orchestrator prompt (which lives in system.md and is loaded by
loader.py), the analyzer prompt is assembled dynamically from live state data
at the time of invocation.  It is intentionally narrow: the analyzer receives
only the context it needs for one focused task and nothing else.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional


def build_analyzer_prompt(
    design_name: str,
    uncovered_items: List[Dict[str, Any]],
    rtl_snippets: Dict[str, str],
    previous_attempts: Optional[str],
    coverage_phase: Optional[str],
) -> str:
    """
    Build the system prompt for the analyzer agent.

    The prompt is structured in four sections:

    1. Role and objective — tells the analyzer exactly what it is and what
       it must produce.
    2. Design context — RTL snippets for the files/modules relevant to the
       uncovered items so the analyzer can reason about signal behaviour.
    3. Uncovered items — the specific bins (functional coverage) or lines
       (code coverage) that need to be hit, with as much hierarchy context
       as is available.
    4. Previous attempts — a brief summary of what stimulus has already been
       tried so the analyzer can avoid repeating failed approaches.

    Args:
        design_name:       Name of the design under verification.
        uncovered_items:   List of dicts describing each uncovered item.
                           For functional coverage each dict has keys:
                             'covergroup', 'coverpoint', 'bin', 'coverage_pct'
                           For code coverage each dict has keys:
                             'file', 'line_number', 'source_text'
        rtl_snippets:      Dict mapping file paths to relevant RTL source
                           text extracted from the design files.  The caller
                           is responsible for trimming these to a reasonable
                           size before passing them in.
        previous_attempts: A plain-text summary of stimulus patterns that
                           have already been tried without success, or None
                           if this is the first analysis request.
        coverage_phase:    "code" or "functional" — determines how the
                           uncovered items are described in the prompt.

    Returns:
        Complete system prompt string for the analyzer LLM call.
    """
    phase_label = "functional coverage bins" if coverage_phase == "functional" else "code coverage lines"

    # ── Section 1: Role ───────────────────────────────────────────────────
    role_section = f"""You are a hardware verification expert specialising in SystemVerilog coverage analysis.

Your task is to analyse uncovered {phase_label} for the design '{design_name}' and produce a concrete, actionable stimulus recommendation that an LLM-driven testbench generator can implement directly.

You have access to:
- The relevant RTL source code
- The list of uncovered items with full hierarchy context
- A summary of stimulus approaches that have already been tried

Your output must be a structured recommendation with the following sections:
1. ROOT CAUSE — For each uncovered item, explain in one or two sentences exactly why the existing stimulus has not hit it. Reference specific signal names, FSM states, or timing conditions from the RTL.
2. STIMULUS STRATEGY — For each uncovered item, describe the precise sequence of signal assertions required to hit it. Be specific: name the registers to write, the values to use, and the timing relative to other signals.
3. PRIORITY ORDER — List the uncovered items in order from easiest to hardest to hit, with a one-line justification for each ranking.
4. WAIVE CANDIDATES — If any uncovered item appears architecturally unreachable (e.g. requires simultaneous assertion of mutually exclusive signals, or depends on a counter that cannot roll over within the simulation budget), flag it explicitly with a reason.

Be concise. The testbench generator will implement your recommendations directly."""

    # ── Section 2: RTL context ─────────────────────────────────────────────
    if rtl_snippets:
        rtl_parts = []
        for file_path, snippet in rtl_snippets.items():
            rtl_parts.append(f"### {Path(file_path).name}\n```verilog\n{snippet}\n```")
        rtl_section = "## RELEVANT RTL\n\n" + "\n\n".join(rtl_parts)
    else:
        rtl_section = "## RELEVANT RTL\n\n(No RTL snippets provided)"

    # ── Section 3: Uncovered items ─────────────────────────────────────────
    if not uncovered_items:
        items_section = f"## UNCOVERED {phase_label.upper()}\n\n(None — nothing to analyse)"
    elif coverage_phase == "functional":
        items_lines = []
        for i, item in enumerate(uncovered_items, start=1):
            cg   = item.get("covergroup", "unknown")
            cp   = item.get("coverpoint", "unknown")
            bn   = item.get("bin", "unknown")
            pct  = item.get("coverage_pct", 0.0)
            items_lines.append(
                f"{i}. Covergroup: {cg}\n"
                f"   Coverpoint: {cp}\n"
                f"   Bin:        {bn}\n"
                f"   Covergroup coverage so far: {pct:.1f}%"
            )
        items_section = (
            f"## UNCOVERED FUNCTIONAL COVERAGE BINS\n\n"
            + "\n\n".join(items_lines)
        )
    else:
        items_lines = []
        for i, item in enumerate(uncovered_items, start=1):
            fname = item.get("file", "unknown")
            lnum  = item.get("line_number", "?")
            src   = item.get("source_text", "(source unavailable)")
            items_lines.append(
                f"{i}. File: {fname}\n"
                f"   Line {lnum}: {src}"
            )
        items_section = (
            f"## UNCOVERED CODE COVERAGE LINES\n\n"
            + "\n\n".join(items_lines)
        )

    # ── Section 4: Previous attempts ──────────────────────────────────────
    if previous_attempts:
        attempts_section = (
            "## PREVIOUS STIMULUS ATTEMPTS (already tried — do not repeat)\n\n"
            + previous_attempts
        )
    else:
        attempts_section = (
            "## PREVIOUS STIMULUS ATTEMPTS\n\n"
            "No previous attempts recorded — this is the first analysis request."
        )

    # ── Assemble ───────────────────────────────────────────────────────────
    return "\n\n".join([
        role_section,
        rtl_section,
        items_section,
        attempts_section,
    ])
