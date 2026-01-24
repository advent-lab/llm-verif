from pathlib import Path
from typing import Dict, Any

def load_system_prompt(
    design_name: str,
    design_dir: Path,
    spec_path: Path,
    rtl_dir: Path,
    rtl_files: list[str],
    module_header: str,
    work_dir: Path,
    design_context_enabled: bool,
    testplan_enabled: bool,
    max_iterations: int,
    sim_runs: int
) -> str:
    """
    Load system prompt template and interpolate variables.

    Returns complete system prompt string.
    """
    # Read template
    template_path = Path(__file__).parent / "system.md"
    with open(template_path, 'r', encoding='utf-8') as f:
        full_content = f.read()

    # Extract template content (between ``` markers after "System Prompt Template")
    # Find the start of the template (after "## System Prompt Template")
    start_marker = "## System Prompt Template\n\n```"
    start_idx = full_content.find(start_marker)
    if start_idx == -1:
        raise ValueError("Could not find template start marker")

    # Move past the marker and opening ```
    start_idx += len(start_marker) + 1  # +1 for newline after ```

    # Find the end marker (closing ``` before "## Conditional Sections")
    end_marker = "```\n\n---\n\n## Conditional Sections"
    end_idx = full_content.find(end_marker, start_idx)
    if end_idx == -1:
        raise ValueError("Could not find template end marker")

    template = full_content[start_idx:end_idx]

    # Prepare conditional sections
    if testplan_enabled:
        testplan_instruction = """### Step 2: Create Verification Plan
Before generating testbenches, create a verification plan that outlines:
- Key features to test
- Corner cases and boundary conditions
- Reset and initialization scenarios
- Error conditions to verify
- Expected coverage targets per feature

Save your testplan using `write_file` to `testplan.md`

This plan will guide your testbench development and help ensure comprehensive coverage."""
    else:
        testplan_instruction = "(Testplan generation is disabled - proceed directly to testbench generation)"

    if design_context_enabled:
        design_context_access = "ENABLED"
        design_context_instruction = f"""**RTL Access:** ENABLED  
You can read the RTL source files to understand implementation details.
Use `read_file` on files in {rtl_dir}/ when you need to:
- Understand how to trigger specific code paths
- See the exact conditions for uncovered branches
- Understand state machine implementations
- Trace signal connections between modules

This is especially useful when trying to cover specific lines shown in coverage reports."""
    else:
        design_context_access = "DISABLED"
        design_context_instruction = f"""**RTL Access:** DISABLED  
You cannot read files in the {rtl_dir}/ directory.
Generate stimulus based solely on:
- The specification document
- The module interface shown above
- Coverage feedback (uncovered line numbers, but not source)

Focus on black-box testing: exercise all specified functionality through the ports."""

    # Interpolate variables
    prompt = template.format(
        design_name=design_name,
        design_dir=str(design_dir),
        spec_path=str(spec_path),
        rtl_dir=str(rtl_dir),
        rtl_file_list=", ".join(rtl_files),
        module_header=module_header,
        work_dir=str(work_dir),
        design_context_access=design_context_access,
        design_context_instruction=design_context_instruction,
        testplan_instruction=testplan_instruction,
        max_iterations=max_iterations,
        sim_runs=sim_runs
    )

    return prompt
