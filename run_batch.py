#!/usr/bin/env python3
"""
Top-level batch runner: runs run_agent_design_batch.py for each design
in DESIGNS sequentially, each with NUM_RUNS parallel agent runs.

Usage:
    python run_batch.py <num_runs>
    python run_batch.py 4

Edit the DESIGNS list below to select which designs to run.
All other configuration is read from eval.env.
"""

import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Edit this list to select which designs to run.
# Design names must match subdirectory names under data/.
# ---------------------------------------------------------------------------
DESIGNS = [
    # "chacha_top",
    # "ethmac_eth_with_cop",
    # "SD-card-controller_top",
    "sha1_top",
    # "trng_top",
    "float_adder",
    "cryptech_uart",
    "pooling",
    "cvdp_agentic_rgb_color_space_conversion",
    # "cvdp_agentic_spi_complex_mult",
    "float_multiplier",
    # "cvdp_agentic_poly_interpolator",
    # "cvdp_agentic_sorter",
    # "cvdp_agentic_memory_scheduler",
    # "cvdp_agentic_ttc_lite",
]
# ---------------------------------------------------------------------------


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <num_runs>")
        sys.exit(1)

    try:
        num_runs = int(sys.argv[1])
    except ValueError:
        print(f"Error: num_runs must be an integer, got '{sys.argv[1]}'")
        sys.exit(1)

    if num_runs < 1:
        print("Error: num_runs must be >= 1")
        sys.exit(1)

    script_dir = Path(__file__).parent
    design_batch_script = script_dir / "run_agent_design_batch.py"
    if not design_batch_script.exists():
        print(f"Error: run_agent_design_batch.py not found at {design_batch_script}")
        sys.exit(1)

    print(f"Designs   : {len(DESIGNS)}")
    print(f"Runs each : {num_runs}")
    print(f"Total runs: {len(DESIGNS) * num_runs}")
    print("=" * 70)

    results: list[tuple[str, int]] = []
    for idx, design in enumerate(DESIGNS, start=1):
        print(f"\n[{idx}/{len(DESIGNS)}] Design: {design}")
        print("-" * 70)
        returncode = subprocess.call(
            [sys.executable, str(design_batch_script), design, str(num_runs)]
        )
        results.append((design, returncode))

    print()
    print("=" * 70)
    print("BATCH COMPLETE")
    print("=" * 70)
    succeeded = [d for d, rc in results if rc == 0]
    failed = [d for d, rc in results if rc != 0]
    print(f"Succeeded ({len(succeeded)}): {', '.join(succeeded) if succeeded else 'none'}")
    if failed:
        print(f"Failed    ({len(failed)}): {', '.join(failed)}")
    print()

    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
