"""
Critic Agent Prompt Templates

The Critic agent performs pre-simulation quality assessment to catch errors
before expensive simulation runs.
"""

import json
from typing import Dict, Any


def build_critique_prompt(design_spec: str, testbench_code: str, verification_plan: Dict[str, Any]) -> str:
    """
    Build prompt for Critic agent to review testbench quality.

    Args:
        design_spec: Design specification text
        testbench_code: SystemVerilog testbench code to review
        verification_plan: Verification plan from Planner agent

    Returns:
        Prompt string for Critic agent
    """

    plan_str = ""
    if verification_plan and verification_plan.get("objectives"):
        objectives = verification_plan.get("objectives", [])
        plan_str = f"\n\nVerification Plan Objectives:\n" + "\n".join(f"- {obj}" for obj in objectives[:5])

    return f"""You are an expert SystemVerilog verification engineer performing code review BEFORE simulation.

Your goal is to catch obvious errors that would waste expensive simulation time.

Design Specification:
{design_spec}
{plan_str}

Generated Testbench Code:
```systemverilog
{testbench_code}
```

Perform a thorough pre-simulation review analyzing:

1. **Syntax & Completeness**:
   - Obvious syntax errors (missing semicolons, unmatched begin/end, etc.)
   - Missing essential components:
     * Clock generation (if design has clk input)
     * Reset sequence (if design has reset/rst input)
     * $finish statement (CRITICAL - prevents timeout)
     * Module instantiation of DUT
     * Signal declarations for all DUT ports

2. **Randomization Quality** (OPTIONAL - info level only):
   - Are random values generated ($urandom, $urandom_range, randomize())?
   - Note: Even simple sequential or fixed patterns are acceptable for initial testing
   - Randomization is nice-to-have, not required for approval

3. **Verilator Compatibility** (CRITICAL):
   - ❌ FORBIDDEN: $urandom_seed() - Verilator does NOT support this
     * Use $urandom() or $urandom_range() instead
     * Do NOT set random seeds in Verilator testbenches
   - ❌ FORBIDDEN: Complex $display formatting with %t (time)
     * Use simple $display("text") or $display("value: %d", value)
   - ❌ FORBIDDEN: Unsupported PLI calls (check Verilator docs)
   - ✅ REQUIRED: Use synthesizable constructs only
   - ✅ REQUIRED: Avoid simulator-specific features

4. **Simulation Risks**:
   - Infinite loops (always blocks without timing control)
   - Potential timeouts (insufficient #delay before $finish)
   - Missing timing controls in sequential logic
   - Unrealistic delays (too long or too short)

5. **Coverage Strategy** (LENIENT - info level only):
   - Does stimulus exercise at least some input values?
   - Note: Perfect coverage isn't required; simulation will reveal gaps
   - Any reasonable attempt at stimulus is acceptable

6. **Best Practices**:
   - Clear variable naming
   - Adequate comments
   - Proper use of initial vs. always blocks
   - Appropriate use of delays

**IMPORTANT**: Be lenient and focus ONLY on errors that WILL cause:
- Compilation failure (especially Verilator incompatibility - use of $urandom_seed is CRITICAL ERROR)
- Simulation crashes or timeouts (missing $finish is CRITICAL)

Minor issues like suboptimal randomization, missing comments, or style preferences should be
marked as "info" only and should NOT prevent approval. The goal is to catch showstoppers, not
to achieve perfection. Remember: a working testbench is better than waiting for a perfect one.

**VERILATOR NOTE**: This testbench will be compiled with Verilator. Any use of $urandom_seed()
or other unsupported PLI calls MUST be flagged as CRITICAL and trigger "reject" recommendation.

Return ONLY valid JSON in this exact format:
{{
  "critique_score": <0-100 integer>,
  "issues": [
    {{"severity": "critical", "category": "missing_finish", "description": "...", "suggestion": "..."}},
    {{"severity": "warning", "category": "randomization", "description": "...", "suggestion": "..."}},
    {{"severity": "info", "category": "best_practice", "description": "...", "suggestion": "..."}}
  ],
  "recommendation": "approve|revise|reject",
  "reasoning": "Brief explanation (1-2 sentences)"
}}

**Severity Levels**:
- **critical**: WILL cause compilation/simulation failure or timeout → triggers "reject" or "revise"
- **warning**: Suboptimal but may work → triggers "revise"
- **info**: Suggestions for improvement only → does not block "approve"

**Category Options**:
missing_finish, missing_clock, missing_reset, syntax_error, infinite_loop, timeout_risk,
poor_randomization, insufficient_stimulus, missing_ports, timing_issue, best_practice,
verilator_incompatible, unsupported_pli

**Score Guidance** (BE LENIENT):
- 80-100: Good enough, approve it → **approve** (minor issues are OK)
- 60-79: Has issues but will likely work → **approve** (let simulation test it)
- 40-59: Significant issues but fixable → **revise** (send to Refiner)
- 0-39: Critical showstoppers only → **reject** (multiple critical compilation/timeout issues)

**Recommendation Decision Tree** (BIAS TOWARD APPROVAL):
- **approve**: score >= 60 AND no CRITICAL issues → proceed to simulation (minor issues OK!)
- **revise**: score 40-59 OR has 1 fixable critical issue → send to Refiner agent
- **reject**: score < 40 AND has multiple critical issues → regenerate with Generator

Remember: Simulation will provide real feedback. Don't block on theoretical concerns!

Be precise and actionable in your feedback. This review saves expensive simulation time!
"""


def build_simple_critique_prompt(testbench_code: str) -> str:
    """
    Simplified critique prompt for quick review (faster, cheaper).

    Args:
        testbench_code: SystemVerilog testbench code

    Returns:
        Simplified prompt for basic checks
    """

    return f"""Quick SystemVerilog testbench review for critical errors:

```systemverilog
{testbench_code[:800]}
```

Check for these CRITICAL issues only:
1. Missing $finish (causes timeout)
2. Missing clock generation
3. Obvious syntax errors
4. Infinite loops

Return JSON:
{{
  "critique_score": <0-100>,
  "has_critical_issues": <true|false>,
  "recommendation": "approve|reject",
  "critical_issue": "description if has_critical_issues=true"
}}

approve if score >= 70, reject if < 70
"""
