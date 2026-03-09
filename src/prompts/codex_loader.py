from pathlib import Path
from typing import Optional

from src.utils.dashboard_loader import get_design_from_dashboard
from src.utils.design_loader import extract_all_module_headers


def load_codex_prompt_from_design(
    design_name: str,
    dashboard_path: Optional[Path] = None,
    base_dir: Optional[Path] = None,
    work_dir: Optional[Path] = None
) -> str:
    """
    Load the Codex prompt template and interpolate variables using a design name.

    Args:
        design_name: Key in dashboard.json for the target design
        dashboard_path: Path to dashboard.json (defaults to project root)
        base_dir: Base directory for resolving $(BASE_DIR) in dashboard (defaults to project_root/data)
        work_dir: Work directory for artifacts (defaults to project_root/work/codex_runs/<design_name>)

    Returns:
        Fully rendered system prompt string
    """
    project_root = Path(__file__).resolve().parents[2]
    dashboard_path = dashboard_path or (project_root / "dashboard.json")
    base_dir = base_dir or (project_root / "data")
    work_dir = work_dir or (project_root / "work" / "codex_runs" / design_name)

    design_config = get_design_from_dashboard(
        dashboard_path=dashboard_path,
        design_name=design_name,
        base_dir=base_dir
    )

    module_header = extract_all_module_headers(design_config.design_files)

    design_dir = design_config.spec_path.parent.parent
    
    # Format file lists for prompt
    design_files_str = "\n".join([f"   - {f}" for f in design_config.design_files])
    if not design_files_str:
        design_files_str = "   (none)"
    
    design_context_files_str = "\n".join([f"   - {f}" for f in design_config.design_context_files])
    if not design_context_files_str:
        design_context_files_str = "   (none)"

    compile_deps_files_str = "\n".join([f"   - {f}" for f in design_config.compile_deps_files])
    if not compile_deps_files_str:
        compile_deps_files_str = "   (none)"

    template_path = Path(__file__).parent / "codex_system.md"
    with open(template_path, "r", encoding="utf-8") as handle:
        full_content = handle.read()

    start_marker = "## System Prompt Template\n\n```"
    start_idx = full_content.find(start_marker)
    if start_idx == -1:
        raise ValueError("Could not find template start marker")

    start_idx += len(start_marker) + 1

    end_marker = "\n```"
    end_idx = full_content.rfind(end_marker)
    if end_idx == -1 or end_idx <= start_idx:
        raise ValueError("Could not find template end marker")

    template = full_content[start_idx:end_idx]

    prompt = template.format(
        design_name=design_config.design_name,
        design_dir=str(design_dir),
        spec_path=str(design_config.spec_path),
        design_files=design_files_str,
        design_context_files=design_context_files_str,
        compile_deps_files=compile_deps_files_str,
        module_header=module_header,
        work_dir=str(work_dir)
    )

    return prompt
