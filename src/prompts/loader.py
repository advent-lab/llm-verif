from pathlib import Path
from typing import Dict, Any, List, Optional

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
    sim_runs: int,
    sim_timeout: int = 60
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
Before generating testbenches, create a verification plan that maps design features to coverage targets:
- Key features and the RTL code paths they exercise
- Corner cases and boundary conditions that may be hard to reach
- Reset and initialization scenarios
- Error conditions and how to trigger them
- For each feature, identify what stimulus is needed to cover it

Save your testplan using `write_file` to `testplan.md`

This plan is your roadmap to 100% coverage — be specific about how you will reach each code path."""
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
        sim_runs=sim_runs,
        sim_timeout=sim_timeout
    )

    return prompt


def _extract_template(file_path: Path) -> str:
    """Extract template content from a prompt markdown file.

    Looks for content between ``` markers after '## System Prompt Template'.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        full_content = f.read()

    start_marker = "## System Prompt Template\n\n```"
    start_idx = full_content.find(start_marker)
    if start_idx == -1:
        raise ValueError(f"Could not find template start marker in {file_path}")

    start_idx += len(start_marker) + 1  # +1 for newline after ```

    # Find closing ``` before next section
    end_marker = "```\n\n---"
    end_idx = full_content.find(end_marker, start_idx)
    if end_idx == -1:
        # Try just closing ```
        end_idx = full_content.rfind("```")
        if end_idx == -1 or end_idx <= start_idx:
            raise ValueError(f"Could not find template end marker in {file_path}")

    return full_content[start_idx:end_idx]


def load_orchestrator_prompt(
    design_name: str,
    module_header: str,
    module_registry_summary: str = "",
    max_iterations: int = 10,
    sim_runs: int = 5,
    sim_timeout: int = 60,
    design_dir: str = "",
    spec_path: str = "",
    design_files: Optional[List] = None,
    design_context_files: Optional[List] = None,
) -> str:
    """Load and interpolate the v2 orchestrator system prompt."""
    template_path = Path(__file__).parent / "orchestrator_system.md"
    template = _extract_template(template_path)

    design_files_str = (
        "\n".join([f"   - {f}" for f in design_files]) if design_files else "   (none)"
    )
    context_files_str = (
        "\n".join([f"   - {f}" for f in design_context_files])
        if design_context_files else "   (none)"
    )

    return template.format(
        design_name=design_name,
        design_dir=design_dir or "(not specified)",
        spec_path=spec_path or "(not specified)",
        design_files=design_files_str,
        design_context_files=context_files_str,
        module_header=module_header,
        module_registry_summary=module_registry_summary or "(not yet extracted)",
        max_iterations=max_iterations,
        sim_runs=sim_runs,
        sim_timeout=sim_timeout,
    )


def load_expert_prompt(
    design_name: str,
    design_dir: Path,
    spec_path: Path,
    design_files: List[Path],
    design_context_files: Optional[List[Path]] = None,
) -> str:
    """Load and interpolate the design expert system prompt."""
    template_path = Path(__file__).parent / "expert_system.md"
    template = _extract_template(template_path)

    design_files_str = "\n".join([f"   - {f}" for f in design_files]) or "   (none)"
    context_files_str = (
        "\n".join([f"   - {f}" for f in design_context_files])
        if design_context_files else "   (none)"
    )

    return template.format(
        design_name=design_name,
        design_dir=str(design_dir),
        spec_path=str(spec_path),
        design_files=design_files_str,
        design_context_files=context_files_str,
    )


def load_generator_prompt() -> str:
    """Load the test generator system prompt (no template variables)."""
    template_path = Path(__file__).parent / "generator_system.md"
    return _extract_template(template_path)


def load_analyzer_generator_prompt(
    design_name: str,
    design_dir: Path,
    spec_path: Path,
    design_files: List[Path],
    design_context_files: Optional[List[Path]] = None,
) -> str:
    """Load and interpolate the analyzer-generator system prompt."""
    template_path = Path(__file__).parent / "analyzer_generator_system.md"
    template = _extract_template(template_path)

    design_files_str = "\n".join([f"   - {f}" for f in design_files]) or "   (none)"
    context_files_str = (
        "\n".join([f"   - {f}" for f in design_context_files])
        if design_context_files else "   (none)"
    )

    return template.format(
        design_name=design_name,
        design_dir=str(design_dir),
        spec_path=str(spec_path),
        design_files=design_files_str,
        design_context_files=context_files_str,
    )


def load_crt_prompt(design_name: str) -> str:
    """Load the CRT agent system prompt."""
    template_path = Path(__file__).parent / "crt_system.md"
    template = _extract_template(template_path)
    return template.format(design_name=design_name)


def load_ag_crt_orchestrator_prompt(
    design_name: str,
    module_header: str,
    module_registry_summary: str = "",
    max_iterations: int = 10,
    sim_runs: int = 5,
    sim_timeout: int = 60,
    design_dir: str = "",
    spec_path: str = "",
    design_files: Optional[List] = None,
    design_context_files: Optional[List] = None,
) -> str:
    """Load and interpolate the v2.1 (AG+CRT) orchestrator system prompt."""
    template_path = Path(__file__).parent / "ag_crt_orchestrator_system.md"
    template = _extract_template(template_path)

    design_files_str = (
        "\n".join([f"   - {f}" for f in design_files]) if design_files else "   (none)"
    )
    context_files_str = (
        "\n".join([f"   - {f}" for f in design_context_files])
        if design_context_files else "   (none)"
    )

    return template.format(
        design_name=design_name,
        design_dir=design_dir or "(not specified)",
        spec_path=spec_path or "(not specified)",
        design_files=design_files_str,
        design_context_files=context_files_str,
        module_header=module_header,
        module_registry_summary=module_registry_summary or "(not yet extracted)",
        max_iterations=max_iterations,
        sim_runs=sim_runs,
        sim_timeout=sim_timeout,
    )
