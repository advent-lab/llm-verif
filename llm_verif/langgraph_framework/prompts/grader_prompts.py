"""
Grader Agent Prompt Templates

The Grader agent performs post-simulation quality assessment to provide
rich feedback beyond simple coverage percentages.
"""

import json
from typing import Dict, Any, List


def build_grading_prompt(
    design_spec: str,
    testbench_code: str,
    sim_results: Dict[str, Any],
    max_coverage: float,
    coverage_history: List[float],
    iteration: int
) -> str:
    """
    Build prompt for Grader agent to assess testbench effectiveness.

    Args:
        design_spec: Design specification
        testbench_code: TestBench code that was simulated
        sim_results: Simulation results dict (coverage, success, feedback)
        max_coverage: Best coverage achieved so far
        coverage_history: List of coverage values from previous iterations
        iteration: Current iteration number

    Returns:
        Prompt string for Grader agent
    """

    current_coverage = sim_results.get("coverage", 0.0)
    coverage_feedback = sim_results.get("coverage_feedback", "N/A")
    error_message = sim_results.get("error_message", "")

    # Calculate improvement
    if len(coverage_history) > 0:
        previous_cov = coverage_history[-1]
        improvement = current_coverage - previous_cov
    else:
        improvement = current_coverage

    # Recent trend
    recent_history_str = str(coverage_history[-5:]) if len(coverage_history) >= 5 else str(coverage_history)

    # Detect plateau
    plateau_detected = False
    if len(coverage_history) >= 3:
        recent = coverage_history[-3:]
        if max(recent) - min(recent) < 1.0:
            plateau_detected = True

    return f"""You are a verification quality grading expert analyzing testbench effectiveness.

Your role is to provide RICH, ACTIONABLE feedback beyond simple coverage percentages.

Design Specification:
{design_spec}

Testbench Code Summary:
- Length: {len(testbench_code)} characters
- Iteration: {iteration}

Simulation Results:
- **Success**: {sim_results.get('success', False)}
- **Current Coverage**: {current_coverage:.2f}%
- **Maximum Coverage Achieved**: {max_coverage:.2f}%
- **Improvement This Iteration**: {improvement:+.2f}%
- **Coverage History (last 5)**: {recent_history_str}
- **Plateau Detected**: {plateau_detected}

Coverage Feedback (Uncovered Areas):
{coverage_feedback}

{f"Error Details: {error_message}" if error_message else ""}

Analyze and grade the testbench on multiple dimensions:

## Grading Criteria

### 1. Coverage Achievement (0-100)
- Actual coverage percentage: {current_coverage:.2f}%
- Progress toward 100% goal
- Improvement over previous iterations

### 2. Test Diversity (0-100)
- Are different test scenarios explored?
- Does stimulus vary sufficiently?
- Are edge cases covered (min/max values, boundaries)?
- Is randomization effective?

### 3. Coverage Strategy Quality (0-100)
- Is the testbench targeting uncovered areas intelligently?
- Are constraints and randomization appropriate?
- Is test duration sufficient?
- Does it exercise the design thoroughly?

### 4. Improvement Trajectory (0-100)
- Rate of coverage improvement (fast/steady/slow/stuck)
- Is progress being made toward 100%?
- Diminishing returns indicator
- Plateau detection

### 5. Gap Analysis
- **What remains uncovered?** {coverage_feedback[:200] if coverage_feedback != "N/A" else ""}
- **Why might it be hard to reach?** (Design complexity, insufficient stimulus, etc.)
- **Are gaps reachable or fundamental barriers?**

## Recommendations for Next Iteration

Based on the analysis, provide SPECIFIC, ACTIONABLE improvements:
- If coverage is improving steadily: continue current approach with minor tweaks
- If stuck at plateau: try different randomization strategy or fresh approach
- If specific areas uncovered: target those with specialized stimulus
- If errors: fix errors before continuing

Return ONLY valid JSON:
{{
  "overall_grade": "A|B|C|D|F",
  "quality_score": <0-100>,
  "coverage_score": <0-100 based on {current_coverage:.2f}%>,
  "diversity_score": <0-100>,
  "strategy_score": <0-100>,
  "improvement_score": <0-100>,
  "gap_analysis": "Detailed analysis of what remains uncovered and why",
  "specific_improvements": [
    "Concrete actionable suggestion 1",
    "Concrete actionable suggestion 2",
    "Concrete actionable suggestion 3"
  ],
  "continue_iteration": true|false,
  "reasoning": "Why continue or stop (2-3 sentences)",
  "plateau_detected": {json.dumps(plateau_detected)},
  "stuck_reason": "Why testbench may be stuck (if plateau_detected=true, else null)"
}}

## Grading Rubric

**Overall Grade**:
- **A (90-100)**: Excellent coverage (>95%) with diverse, effective tests
- **B (80-89)**: Good coverage (80-95%) with solid strategy
- **C (70-79)**: Moderate coverage (60-80%) with room for improvement
- **D (60-69)**: Low coverage (<60%) but making progress
- **F (<60)**: Poor coverage with little/no progress

**Continue Iteration Decision**:
- **true**: Coverage < 100%, making progress (>1% improvement recently), not stuck
- **false**: Coverage = 100% OR stuck (plateau detected) OR fundamental barrier

**Plateau Detection**:
- Stuck if: improvement < 1% over last 3 iterations AND coverage < 95%
- Suggests: need new approach (different randomization, fresh strategy)

Be precise, analytical, and actionable. Your feedback directly influences the next iteration!
"""


def build_simple_grading_prompt(coverage: float, max_coverage: float) -> str:
    """
    Simplified grading for quick assessment.

    Args:
        coverage: Current coverage percentage
        max_coverage: Maximum coverage achieved

    Returns:
        Simple grading prompt
    """

    return f"""Quick testbench grading:

Current Coverage: {coverage:.1f}%
Best Coverage: {max_coverage:.1f}%

Assign grade and decide if iteration should continue.

Return JSON:
{{
  "overall_grade": "A|B|C|D|F",
  "continue_iteration": true|false,
  "reasoning": "Brief reason"
}}

Continue if coverage < 100 and grade >= C.
"""
