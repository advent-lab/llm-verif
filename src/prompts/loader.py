from pathlib import Path
from typing import Dict, Any, List

def load_system_prompt(
    design_name: str,
    design_dir: Path,
    spec_path: Path,
    design_files: List[Path],
    design_context_files: List[Path],
    module_header: str,
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

    # Format file lists for prompt based on design_context_enabled
    if design_context_enabled:
        design_files_str = "\n".join([f"   - {f}" for f in design_files])
        if not design_files_str:
            design_files_str = "   (none)"
        
        design_context_files_str = "\n".join([f"   - {f}" for f in design_context_files])
        if not design_context_files_str:
            design_context_files_str = "   (none)"
        
        file_access_note = "You can read all design and design context files listed above using `read_file` to understand implementation details when needed."
    else:
        design_files_str = "   (not accessible - design context disabled)"
        design_context_files_str = "   (not accessible - design context disabled)"
        file_access_note = "You can only read the specification file. Design and design context files are not accessible for reading."

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

    # Interpolate variables
    prompt = template.format(
        design_name=design_name,
        design_dir=str(design_dir),
        spec_path=str(spec_path),
        design_files=design_files_str,
        design_context_files=design_context_files_str,
        file_access_note=file_access_note,
        module_header=module_header,
        testplan_instruction=testplan_instruction,
        max_iterations=max_iterations,
        sim_runs=sim_runs
    )

    return prompt
