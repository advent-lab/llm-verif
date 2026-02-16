#!/usr/bin/env python3
"""Generate Codex system prompt for a design.

Usage:
    python scripts/gen_codex_prompt.py --design <design_name>
    python scripts/gen_codex_prompt.py --design cvdp_agentic_alu
    python scripts/gen_codex_prompt.py --design cvdp_agentic_spi_complex_mult --output prompt.txt
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.prompts.codex_loader import load_codex_prompt_from_design

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(
        description="Generate Codex system prompt for hardware verification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/gen_codex_prompt.py --design cvdp_agentic_alu
  python scripts/gen_codex_prompt.py --design cvdp_agentic_spi_complex_mult --output prompt.txt
        """
    )
    
    parser.add_argument(
        "--design",
        required=True,
        help="Design name (key in dashboard.json)"
    )
    
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file path (default: print to stdout)"
    )
    
    parser.add_argument(
        "--work-dir",
        type=Path,
        help="Custom work directory (default: work/codex_runs/<design>)"
    )
    
    args = parser.parse_args()
    
    try:
        print(f"Loading design: {args.design}", file=sys.stderr)
        
        prompt = load_codex_prompt_from_design(
            design_name=args.design,
            work_dir=args.work_dir
        )
        
        prompt_length = len(prompt)
        token_estimate = prompt_length // 4
        
        print(f"Generated prompt: {prompt_length} chars (~{token_estimate} tokens)", file=sys.stderr)
        
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(prompt)
            print(f"Saved to: {args.output}", file=sys.stderr)
        else:
            print("\n" + "="*80, file=sys.stderr)
            print(prompt)
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
