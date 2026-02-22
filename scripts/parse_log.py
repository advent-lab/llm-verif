#!/usr/bin/env python3
"""
Parse agent run.log files and extract key metrics.

Usage:
    python scripts/parse_log.py /path/to/run.log
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path


def parse_timestamp(line):
    """Extract timestamp from log line."""
    match = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3})', line)
    if match:
        dt_str = match.group(1)
        ms_str = match.group(2)
        dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
        # Add milliseconds
        ms = int(ms_str) * 1000  # Convert to microseconds
        return dt.replace(microsecond=ms)
    return None


def parse_metrics_line(line):
    """Extract cumulative coverage and tokens from AGENT RESPONSE or API REQUEST line."""
    # Pattern: [... | Cumulative: X% | ... | Tokens: Y (Z%)]
    cumulative_match = re.search(r'Cumulative:\s*([\d.]+)%', line)
    tokens_match = re.search(r'Tokens:\s*([\d,]+)', line)
    
    cumulative = None
    tokens = None
    
    if cumulative_match:
        cumulative = float(cumulative_match.group(1))
    
    if tokens_match:
        # Remove commas from token count
        tokens = int(tokens_match.group(1).replace(',', ''))
    
    return cumulative, tokens


def parse_log_file(log_path):
    """Parse log file and extract metrics."""
    log_path = Path(log_path)
    
    if not log_path.exists():
        raise FileNotFoundError(f"Log file not found: {log_path}")
    
    first_timestamp = None
    last_timestamp = None
    last_metrics_line = None
    warnings = []
    
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            # Get timestamp
            ts = parse_timestamp(line)
            if ts:
                if first_timestamp is None:
                    first_timestamp = ts
                last_timestamp = ts
            
            # Extract warnings
            if 'WARNING:root:' in line:
                # Extract just the warning message
                warning_match = re.search(r'WARNING:root:(.+)$', line)
                if warning_match:
                    warnings.append(warning_match.group(1).strip())
            
            # Check if this is an AGENT RESPONSE or API REQUEST line
            if 'AGENT RESPONSE' in line or 'API REQUEST' in line:
                if 'Cumulative:' in line and 'Tokens:' in line:
                    last_metrics_line = line
    
    if first_timestamp is None or last_timestamp is None:
        raise ValueError("Could not find timestamps in log file")
    
    if last_metrics_line is None:
        raise ValueError("Could not find any AGENT RESPONSE or API REQUEST lines with metrics")
    
    # Calculate time taken
    time_delta = last_timestamp - first_timestamp
    total_seconds = time_delta.total_seconds()
    
    # Extract metrics from last line
    cumulative, tokens = parse_metrics_line(last_metrics_line)
    
    return {
        'start_time': first_timestamp,
        'end_time': last_timestamp,
        'total_seconds': total_seconds,
        'cumulative_coverage': cumulative,
        'final_tokens': tokens,
        'last_metrics_line': last_metrics_line.strip(),
        'warnings': warnings
    }


def format_duration(seconds):
    """Format seconds into human-readable duration."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    elif secs > 0:
        return f"{secs}.{ms:03d}s"
    else:
        return f"{ms}ms"


def main():
    parser = argparse.ArgumentParser(
        description="Parse agent run.log files and extract key metrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python scripts/parse_log.py work/ReAct/trng_top/run.log

Metrics extracted:
  1. Total time taken from start to end
  2. Final token count
  3. Final cumulative coverage achieved
        """
    )
    
    parser.add_argument(
        'log_file',
        type=str,
        help='Path to run.log file'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output in JSON format'
    )
    
    args = parser.parse_args()
    
    try:
        metrics = parse_log_file(args.log_file)
        
        if args.json:
            import json
            output = {
                'start_time': metrics['start_time'].isoformat(),
                'end_time': metrics['end_time'].isoformat(),
                'total_seconds': metrics['total_seconds'],
                'cumulative_coverage': metrics['cumulative_coverage'],
                'final_tokens': metrics['final_tokens'],
                'warnings': metrics['warnings']
            }
            print(json.dumps(output, indent=2))
        else:
            print("=" * 70)
            print("LOG FILE METRICS")
            print("=" * 70)
            print(f"Log file:            {args.log_file}")
            print()
            print(f"Start time:          {metrics['start_time'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
            print(f"End time:            {metrics['end_time'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
            print(f"Total duration:      {format_duration(metrics['total_seconds'])}")
            print()
            print(f"Final coverage:      {metrics['cumulative_coverage']:.1f}%")
            print(f"Final token count:   {metrics['final_tokens']:,}")
            print()
            print("Last metrics line:")
            print(f"  {metrics['last_metrics_line']}")
            print()
            
            # Display warnings
            if metrics['warnings']:
                print(f"Warnings found:      {len(metrics['warnings'])}")
                print("-" * 70)
                for i, warning in enumerate(metrics['warnings'], 1):
                    print(f"{i}. {warning}")
            else:
                print("Warnings found:      None")
            
            print("=" * 70)
        
        return 0
        
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
