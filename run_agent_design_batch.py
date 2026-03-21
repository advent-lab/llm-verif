#!/usr/bin/env python3
"""
Batch runner for parallel agent runs on a single design.

Launches multiple independent run_agent.py processes in parallel for the same
design, each with a unique RUN_ID of the form <design_name>_<run_num>.

Usage:
    python run_agent_design_batch.py <design_name> <num_runs>
    python run_agent_design_batch.py fifo 4

All other configuration is read from eval.env.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _build_run_env_file(base_env_path: Path, design_name: str, run_id: str, dest: Path) -> None:
    """Create a per-run env file from the base, overriding DESIGN_NAME and RUN_ID."""
    lines: list[str] = []
    with base_env_path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            stripped = raw_line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key in ("DESIGN_NAME", "RUN_ID"):
                    continue
            lines.append(raw_line)

    # Append the overridden values
    lines.append(f"\nDESIGN_NAME={design_name}\n")
    lines.append(f"RUN_ID={run_id}\n")

    dest.write_text("".join(lines), encoding="utf-8")


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <design_name> <num_runs>")
        sys.exit(1)

    design_name = sys.argv[1]
    try:
        num_runs = int(sys.argv[2])
    except ValueError:
        print(f"Error: num_runs must be an integer, got '{sys.argv[2]}'")
        sys.exit(1)

    if num_runs < 1:
        print("Error: num_runs must be >= 1")
        sys.exit(1)

    env_file = Path(__file__).parent / "eval.env"
    if not env_file.exists():
        print(f"Error: eval.env not found at {env_file}")
        sys.exit(1)

    run_agent_script = Path(__file__).parent / "run_agent.py"
    if not run_agent_script.exists():
        print(f"Error: run_agent.py not found at {run_agent_script}")
        sys.exit(1)

    print(f"Launching {num_runs} parallel runs for design '{design_name}'")
    print(f"Environment file: {env_file}")
    print("=" * 70)

    # Create a temporary directory for per-run env files
    tmp_dir = Path(tempfile.mkdtemp(prefix="covagent_batch_"))

    processes = []
    tmp_env_files: list[Path] = []
    for run_num in range(1, num_runs + 1):
        run_id = f"{design_name}_{run_num}"
        log_path = Path(__file__).parent / "work" / "logs" /f"{run_id}_batch.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Build a per-run env file with the correct DESIGN_NAME and RUN_ID
        run_env = tmp_dir / f"{run_id}.env"
        _build_run_env_file(env_file, design_name, run_id, run_env)
        tmp_env_files.append(run_env)

        print(f"  Starting run {run_num}/{num_runs}: RUN_ID={run_id}")

        log_file = open(log_path, "w")
        proc = subprocess.Popen(
            [sys.executable, str(run_agent_script), "--env-file", str(run_env)],
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        processes.append((run_id, proc, log_file))

    print()
    print(f"All {num_runs} runs launched. Waiting for completion...")
    print()

    results = []
    for run_id, proc, log_file in processes:
        returncode = proc.wait()
        log_file.close()
        status = "SUCCESS" if returncode == 0 else f"FAILED (exit {returncode})"
        results.append((run_id, returncode))
        print(f"  {run_id}: {status}")

    # Clean up temporary env files
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)

    print()
    print("=" * 70)
    succeeded = sum(1 for _, rc in results if rc == 0)
    failed = sum(1 for _, rc in results if rc != 0)
    print(f"Results: {succeeded} succeeded, {failed} failed out of {num_runs} runs")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
