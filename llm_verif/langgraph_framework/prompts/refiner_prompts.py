"""
Refiner Agent Prompt Templates

The Refiner agent synthesizes feedback from multiple sources (Critic, Grader, Simulator)
to make targeted improvements to the testbench.
"""

import json
from typing import Dict, Any, Optional


def build_refinement_prompt(
    current_testbench: str,
    design_spec: str,
    module_header: str,
    critique: Optional[Dict[str, Any]] = None,
    grading: Optional[Dict[str, Any]] = None,
    sim_results: Optional[Dict[str, Any]] = None
) -> str:
    """
    Build comprehensive refinement prompt with multi-agent feedback.

    Args:
        current_testbench: Current testbench code to refine
        design_spec: Design specification
        module_header: Module header/interface
        critique: Critique results from Critic agent
        grading: Grading results from Grader agent
        sim_results: Simulation results

    Returns:
        Refinement prompt string
    """

    # Build feedback sections
    critique_section = ""
    if critique and critique.get("issues"):
        issues_str = "\n".join(
            f"  - [{issue['severity'].upper()}] {issue['category']}: {issue['description']}\n    → Suggestion: {issue['suggestion']}"
            for issue in critique["issues"][:5]  # Top 5 issues
        )
        critique_section = f"""
## Critic Review Feedback

Score: {critique.get('critique_score', 'N/A')}/100
Recommendation: {critique.get('recommendation', 'N/A')}

Issues Identified:
{issues_str}

Reasoning: {critique.get('reasoning', '')}
"""

    grading_section = ""
    if grading:
        improvements_str = "\n".join(
            f"  {i+1}. {imp}"
            for i, imp in enumerate(grading.get("specific_improvements", [])[:5])
        )
        grading_section = f"""
## Grader Assessment Feedback

Overall Grade: {grading.get('overall_grade', 'N/A')}
Quality Score: {grading.get('quality_score', 'N/A')}/100
Coverage Score: {grading.get('coverage_score', 'N/A')}/100
Diversity Score: {grading.get('diversity_score', 'N/A')}/100

Gap Analysis:
{grading.get('gap_analysis', '')}

Specific Improvements Recommended:
{improvements_str}

Plateau Detected: {grading.get('plateau_detected', False)}
{f"Stuck Reason: {grading['stuck_reason']}" if grading.get('stuck_reason') else ''}
"""

    sim_section = ""
    if sim_results:
        sim_section = f"""
## Simulation Results

Success: {sim_results.get('success', False)}
Coverage: {sim_results.get('coverage', 0.0):.2f}%
Error Code: {sim_results.get('error_code', 0)}

Coverage Feedback (Uncovered Areas):
{sim_results.get('coverage_feedback', 'N/A')[:500]}

{f"Error Message: {sim_results.get('error_message', '')}" if sim_results.get('error_message') else ''}
"""

    # Determine refinement strategy
    strategy_guidance = _determine_refinement_strategy(critique, grading, sim_results)

    return f"""You are refining a SystemVerilog testbench based on comprehensive feedback from multiple expert agents.

Design Specification:
{design_spec}

Module Interface:
{module_header}

Current Testbench:
```systemverilog
{current_testbench}
```

# Multi-Agent Feedback
{critique_section}
{grading_section}
{sim_section}

# Refinement Strategy Guidance

{strategy_guidance}

# Your Task

Based on ALL the feedback above, refine the testbench to address the issues and improve coverage.

**Prioritization**:
1. **CRITICAL ISSUES FIRST**: Fix any critical issues from Critic (missing $finish, syntax errors, etc.)
2. **COVERAGE GAPS**: Address specific uncovered areas identified in simulation feedback
3. **QUALITY IMPROVEMENTS**: Apply suggestions from Grader for better test diversity
4. **OPTIMIZATION**: Improve randomization strategy if stuck at plateau

**Refinement Guidelines**:
- If Critic found critical issues → fix those immediately (syntax, missing components)
- If simulation shows specific uncovered lines → add stimulus to target those lines
- If Grader detected plateau → try a DIFFERENT approach (new randomization strategy, different test patterns)
- If coverage is improving steadily → continue current approach with minor enhancements
- Maintain testbench structure and readability
- Add comments explaining your changes

Return ONLY valid JSON in this format:
{{
  "test bench": "...complete refined SystemVerilog testbench code...",
  "comments": "Brief summary of key changes made (2-3 sentences)",
  "refinement_strategy": "fix_errors|add_coverage|new_approach|optimize"
}}

**refinement_strategy options**:
- **fix_errors**: Addressing compilation/simulation errors
- **add_coverage**: Adding stimulus for uncovered areas
- **new_approach**: Trying fundamentally different test strategy (if stuck)
- **optimize**: Fine-tuning existing approach

Generate a complete, working testbench that addresses the feedback!
"""


def _determine_refinement_strategy(
    critique: Optional[Dict[str, Any]],
    grading: Optional[Dict[str, Any]],
    sim_results: Optional[Dict[str, Any]]
) -> str:
    """
    Determine the appropriate refinement strategy based on feedback.

    Returns:
        Strategy guidance string
    """

    # Check for critical issues from Critic
    if critique:
        critical_issues = [
            issue for issue in critique.get("issues", [])
            if issue.get("severity") == "critical"
        ]
        if critical_issues:
            return """**PRIORITY: Fix Critical Issues**

The Critic identified critical issues that MUST be fixed first:
- Focus on fixing syntax errors, missing components ($finish, clock, reset)
- Ensure the testbench will compile and run without errors
- Once fixed, then focus on coverage improvements

**Strategy**: fix_errors
"""

    # Check for simulation errors
    if sim_results and not sim_results.get("success"):
        error_code = sim_results.get("error_code", 0)
        if error_code == 1:
            return "**PRIORITY: Fix Compilation Errors**\n\nAddress the compilation errors shown in the error message.\n\n**Strategy**: fix_errors"
        elif error_code == 2:
            return "**PRIORITY: Fix Simulation Errors**\n\nThe testbench compiles but crashes during simulation. Fix runtime errors.\n\n**Strategy**: fix_errors"
        elif error_code == 3:
            return "**PRIORITY: Fix Timeout**\n\nThe simulation timed out. Ensure $finish is called and reduce test duration if needed.\n\n**Strategy**: fix_errors"

    # Check for plateau (stuck)
    if grading and grading.get("plateau_detected"):
        return """**PRIORITY: Break Through Plateau**

The Grader detected that coverage has plateaued (< 1% improvement over 3 iterations).
Current approach is NOT working. You need a DIFFERENT strategy:

- Try different randomization patterns (different ranges, distributions)
- Use different test patterns (corner cases, specific sequences)
- Increase test duration or number of test cases
- Target specific uncovered areas with directed tests (not just random)

**Strategy**: new_approach
"""

    # Normal coverage improvement
    if sim_results and sim_results.get("success"):
        coverage = sim_results.get("coverage", 0)
        if coverage < 100:
            return """**PRIORITY: Improve Coverage**

Add stimulus to target the uncovered areas shown in the coverage feedback.
- Analyze which lines/blocks are not covered
- Add test cases that exercise those paths
- Ensure randomization reaches all input combinations
- Consider edge cases and boundary conditions

**Strategy**: add_coverage
"""

    # Default: optimization
    return """**PRIORITY: Optimize Testbench**

Continue refining the current approach:
- Enhance randomization quality
- Improve test diversity
- Optimize for better coverage efficiency

**Strategy**: optimize
"""
