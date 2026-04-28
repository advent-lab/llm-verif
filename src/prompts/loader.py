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


def load_functional_system_prompt(
    design_name: str,
    design_dir: Path,
    spec_path: Path,
    design_files: List[Path],
    design_context_files: List[Path],
    module_header: str,
    design_context_enabled: bool,
    testbench_template_path: Optional[Path],
    coverage_target: float,
    max_iterations: int,
    sim_runs: int,
    sim_timeout: int = 60
) -> str:
    """Load and interpolate the functional coverage system prompt."""
    template_path = Path(__file__).parent / "system_functional.md"

    with open(template_path, 'r', encoding='utf-8') as f:
        full_content = f.read()

    start_marker = "## System Prompt Template\n\n```"
    start_idx = full_content.find(start_marker)
    if start_idx == -1:
        raise ValueError("Could not find template start marker in system_functional.md")
    start_idx += len(start_marker) + 1

    end_marker = "```\n\n---"
    end_idx = full_content.find(end_marker, start_idx)
    if end_idx == -1:
        end_idx = full_content.rfind("```")
    template = full_content[start_idx:end_idx]

    if design_context_enabled:
        design_files_str = "\n".join([f"   - {f}" for f in design_files]) or "   (none)"
        design_context_files_str = "\n".join([f"   - {f}" for f in design_context_files]) or "   (none)"
        file_access_note = "You can read all design and design context files listed above using `read_file`."
    else:
        design_files_str = "   (not accessible - design context disabled)"
        design_context_files_str = "   (not accessible - design context disabled)"
        file_access_note = "You can only read the specification and testbench template. Design files are not accessible."

    tb_template_str = str(testbench_template_path) if testbench_template_path else "(not provided)"

    return template.format(
        design_name=design_name,
        design_dir=str(design_dir),
        spec_path=str(spec_path),
        design_files=design_files_str,
        design_context_files=design_context_files_str,
        file_access_note=file_access_note,
        module_header=module_header,
        testbench_template_path=tb_template_str,
        coverage_target=coverage_target,
        max_iterations=max_iterations,
        sim_runs=sim_runs,
        sim_timeout=sim_timeout
    )


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


_V3_MODE_SECTIONS = {
    "crt": {
        "intro": (
            "You generate broad, randomized stimulus to sweep coverage cheaply "
            "early in verification. Variety beats precision in CRT mode — try "
            "lots of distributions, modes, and timing patterns."
        ),
        "strategy": (
            "Write testbenches that drive heavily randomized inputs through the "
            "DUT's top-level ports. Use `$urandom` / `$urandom_range` aggressively. "
            "Across rounds, deliberately vary the seed family, the distribution "
            "shape (uniform vs. weighted), and the operating mode (e.g., reset "
            "variants, mode-control bit combinations). Don't analyze coverage "
            "holes deeply — just keep widening the stimulus space."
        ),
    },
    "directed": {
        "intro": (
            "You generate targeted stimulus aimed at specific uncovered code "
            "paths or functional bins. Precision beats variety in directed mode "
            "— each testbench should drive a clearly-named scenario."
        ),
        "strategy": (
            "Read the testplan in your task message carefully. For each round, "
            "pick ONE hole or scenario from the testplan, trace what input "
            "sequence triggers it (using your whitelisted RTL files), write a "
            "testbench that walks exactly that sequence, and check whether the "
            "hole closed. If a hole resists 2 rounds, document it in your "
            "summary and move on."
        ),
    },
}


def load_orc_gen_orchestrator_prompt(
    design_name: str,
    module_header: str,
    module_registry_summary: str = "",
    max_iterations: int = 10,
    sim_runs: int = 5,
    sim_timeout: int = 60,
    gen_max_iterations: int = 5,
    design_dir: str = "",
    spec_path: str = "",
    design_files: Optional[List] = None,
    design_context_files: Optional[List] = None,
) -> str:
    """Load and interpolate the v3 (orc_gen) orchestrator system prompt."""
    template_path = Path(__file__).parent / "orc_gen_orchestrator_system.md"
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
        gen_max_iterations=gen_max_iterations,
    )


def load_orc_gen_test_generator_prompt(
    mode: str,
    design_name: str,
    spec_path: str,
    allowed_files: Optional[List[str]] = None,
    gen_max_iterations: int = 5,
    gen_max_retries: int = 3,
    sim_timeout: int = 60,
) -> str:
    """Load and interpolate the v3 test generator system prompt.

    Args:
        mode: "crt" or "directed" — selects the mode-specific intro/strategy.
        design_name: Design name for prompt interpolation.
        spec_path: Path to the spec (informational; the orchestrator may include
            it in the read whitelist).
        allowed_files: Whitelist of absolute paths the generator may read_file.
        gen_max_iterations: Max successful coverage rounds inside this dispatch.
        gen_max_retries: Max compile/sim failures before stopping.
        sim_timeout: Per-run sim timeout in seconds.
    """
    mode_key = mode.lower().strip()
    if mode_key not in _V3_MODE_SECTIONS:
        raise ValueError(
            f"Unknown v3 generator mode: {mode!r} (expected 'crt' or 'directed')"
        )

    template_path = Path(__file__).parent / "orc_gen_test_generator_system.md"
    template = _extract_template(template_path)

    if allowed_files:
        allowed_block = "\n".join(f"   - {p}" for p in allowed_files)
    else:
        allowed_block = "   (no files allowed — operate purely from your task message)"

    return template.format(
        mode=mode_key,
        mode_intro=_V3_MODE_SECTIONS[mode_key]["intro"],
        mode_strategy=_V3_MODE_SECTIONS[mode_key]["strategy"],
        design_name=design_name,
        spec_path=spec_path or "(not specified)",
        allowed_files_block=allowed_block,
        gen_max_iterations=gen_max_iterations,
        gen_max_retries=gen_max_retries,
        sim_timeout=sim_timeout,
    )


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
