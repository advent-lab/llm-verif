#!/usr/bin/env python3

import os
import sys
import shutil
import subprocess
import csv
from pathlib import Path
from datetime import datetime

# Configuration
ENV_FILE = "/home/snlad/capstone/llm-verif/llm_verif/sol.env"
DESIGNS_BASE_DIR = "/home/snlad/capstone/llm-verif/data"
WORK_DIR = "/home/snlad/capstone/llm-verif/llm_verif/work"
OUTPUT_FILE = os.path.join(WORK_DIR, "regression_output.csv")
BASELINE_FILE = os.path.join(WORK_DIR, "baseline.csv")

# List of designs to test in batch mode
DESIGNS = [
    "fifo"
]


def backup_env():
    """Create a backup of the environment file."""
    shutil.copy(ENV_FILE, f"{ENV_FILE}.backup")


def restore_env():
    """Restore the environment file from backup."""
    backup_path = f"{ENV_FILE}.backup"
    if os.path.exists(backup_path):
        shutil.copy(backup_path, ENV_FILE)


def read_env_file():
    """Read the environment file and return a dictionary of parameters."""
    env_params = {}
    try:
        with open(ENV_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    env_params[key.strip()] = value.strip()
    except Exception as e:
        print(f"Warning: Could not read environment file: {e}")
    return env_params


def get_simulator():
    """Get the simulator from the environment file."""
    env_params = read_env_file()
    simulator = env_params.get('SIMULATOR', '').lower()
    
    if simulator not in ['questasim', 'verilator']:
        print(f"Warning: Unknown or missing simulator '{simulator}'. Defaulting to 'questasim'")
        return 'questasim'
    
    return simulator


def update_env_file(design_path):
    """Update the DESIGN and ID variables in the environment file."""
    design_name = os.path.basename(design_path)
    
    # Read the current file
    with open(ENV_FILE, 'r') as f:
        lines = f.readlines()
    
    # Update the lines
    with open(ENV_FILE, 'w') as f:
        for line in lines:
            if line.startswith('DESIGN='):
                f.write(f'DESIGN={design_path}\n')
            elif line.startswith('ID='):
                f.write(f'ID={design_name}_gpt4o-mini\n')
            else:
                f.write(line)


def run_design(design):
    """Run llm_verif for a specific design based on the simulator."""
    design_path = os.path.join(DESIGNS_BASE_DIR, design)
    
    # Check if design directory exists
    if not os.path.isdir(design_path):
        print(f"Error: Design directory '{design}' not found at {design_path}")
        return False
    
    update_env_file(design_path)
    
    # Get simulator from env file
    simulator = get_simulator()
    print(f"Using simulator: {simulator}")
    
    # Run llm_verif command based on simulator
    try:
        if simulator == 'verilator':
            cmd = ['llm_verif', '--dotenv_path', ENV_FILE, '--backend=openai']
        else:  # questasim
            cmd = ['llm_verif', '--dotenv_path', ENV_FILE]
        
        print(f"Running command: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        print(f"Error: llm_verif failed for design '{design}'")
        return False


def get_latest_csv_for_design(design_name, work_path):
    """Get the most recent CSV file for a specific design based on modification time."""
    # Pattern to match CSV files for this design
    csv_files = []
    
    for csv_file in work_path.glob("*.csv"):
        # Skip the output file itself and baseline
        if csv_file.name in ["regression_output.csv", "baseline.csv"]:
            continue
        
        # Check if this CSV is for the current design by reading its content
        try:
            with open(csv_file, 'r', newline='') as f:
                reader = csv.reader(f)
                rows = list(reader)
                if len(rows) > 1:
                    # Check if design name matches (first column of last row)
                    last_row = rows[-1]
                    if len(last_row) > 0 and last_row[0] == design_name:
                        csv_files.append(csv_file)
        except Exception as e:
            print(f"Error reading {csv_file.name}: {e}")
            continue
    
    if not csv_files:
        return None
    
    # Return the most recently modified file
    latest_file = max(csv_files, key=lambda f: f.stat().st_mtime)
    return latest_file


def extract_csv_columns():
    """Extract specific columns from the latest CSV files and create regression output."""
    print(f"\nExtracting columns from latest CSV files in {WORK_DIR}...")
    
    # Read environment file to get additional parameters
    env_params = read_env_file()
    
    # Create header row
    headers = [
        "Design",
        "temperature funct",
        "testplan",
        "b5",
        "remove polluted context",
        "run",
        "iteration",
        "batch",
        "temperature",
        "statement coverage",
        "max total coverage",
        "average total coverage",
        "run merged coverage",
        "cross run merged coverage"
    ]
    
    # Column indices to extract (0-indexed: 0, 4, 5, 6, 7, 8, 9, 10, 11, 19, 22, 23, 24, 25)
    column_indices = [0, 4, 5, 6, 7, 8, 9, 10, 11, 19, 22, 23, 24, 25]
    
    # Track which designs we've processed
    processed_designs = {}
    
    work_path = Path(WORK_DIR)
    if not work_path.exists():
        print(f"Warning: Work directory {WORK_DIR} does not exist")
        return
    
    # First pass: identify all unique designs and their latest CSV files
    all_csv_files = [f for f in work_path.glob("*.csv") 
                     if f.name not in ["regression_output.csv", "baseline.csv"]]
    
    design_to_latest_csv = {}
    
    for csv_file in all_csv_files:
        try:
            with open(csv_file, 'r', newline='') as f:
                reader = csv.reader(f)
                rows = list(reader)
                if len(rows) > 1:
                    last_row = rows[-1]
                    design_name = last_row[0] if len(last_row) > 0 else ""
                    
                    if design_name:
                        mod_time = csv_file.stat().st_mtime
                        if design_name not in design_to_latest_csv or mod_time > design_to_latest_csv[design_name][1]:
                            design_to_latest_csv[design_name] = (csv_file, mod_time, last_row)
        except Exception as e:
            print(f"Error processing {csv_file.name}: {e}")
    
    # Write output
    with open(OUTPUT_FILE, 'w', newline='') as outfile:
        writer = csv.writer(outfile)
        writer.writerow(headers)
        
        # Process only the designs that were specified in DESIGNS list
        for design_name in sorted(design_to_latest_csv.keys()):
            # Only include designs from the DESIGNS list
            if design_name not in DESIGNS:
                print(f"Skipping '{design_name}' (not in current DESIGNS list)")
                continue
            
            csv_file, mod_time, last_row = design_to_latest_csv[design_name]
            
            print(f"Processing latest CSV for '{design_name}': {csv_file.name} "
                  f"(modified: {datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')})")
            
            # Extract specified columns
            extracted_data = [
                last_row[i] if i < len(last_row) else ""
                for i in column_indices
            ]
            writer.writerow(extracted_data)
        
        # Add separation row
        writer.writerow([])
        
        # Add environment parameters table
        writer.writerow(["SIMULATOR", env_params.get('SIMULATOR', 'N/A')])
        writer.writerow(["RUNS", env_params.get('RUNS', 'N/A')])
        writer.writerow(["MAX_ITERATIONS", env_params.get('MAX_ITERATIONS', 'N/A')])
        writer.writerow(["MAX_VALID_ITER", env_params.get('MAX_VALID_ITER', 'N/A')])
        writer.writerow(["BATCH_SIZE", env_params.get('BATCH_SIZE', 'N/A')])
        writer.writerow(["SIM_RUNS", env_params.get('SIM_RUNS', 'N/A')])
    
    print(f"\nRegression output created: {OUTPUT_FILE}")
    
    # Display summary
    print(f"Output contains {len(design_to_latest_csv)} design(s) + 1 header row")


def compare_with_baseline():
    """Compare regression output with baseline and append comparison to the same file."""
    if not os.path.exists(BASELINE_FILE):
        print(f"\nNo baseline file provided.")
        return
    
    print(f"\nBaseline file found. Comparing results with baseline...")
    
    # Read baseline and regression output
    baseline_data = {}
    regression_data = {}
    
    # Known parameter keys that should be skipped
    skip_keys = {'SIMULATOR', 'RUNS', 'MAX_ITERATIONS', 'MAX_VALID_ITER', 
                 'BATCH_SIZE', 'SIM_RUNS', '=== COMPARISON WITH BASELINE ===', ''}
    
    try:
        with open(BASELINE_FILE, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                design = row.get('Design', '').strip()
                # Skip empty rows, parameter rows, and header rows
                if design and design not in skip_keys:
                    baseline_data[design] = row
        
        # Read current regression output (before we append comparison)
        with open(OUTPUT_FILE, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                design = row.get('Design', '').strip()
                # Skip empty rows, parameter rows, and header rows
                if design and design not in skip_keys:
                    regression_data[design] = row
    except Exception as e:
        print(f"Error reading CSV files: {e}")
        return
    
    # Coverage metrics to compare
    coverage_metrics = [
        ('statement coverage', 'Statement Coverage'),
        ('max total coverage', 'Max Total Coverage'),
        ('average total coverage', 'Average Total Coverage'),
        ('run merged coverage', 'Run Merged Coverage'),
        ('cross run merged coverage', 'Cross Run Merged Coverage')
    ]
    
    comparison_headers = [
        'Design',
        'Metric',
        'Baseline',
        'New',
        'Difference',
        '% Change'
    ]
    
    improved_designs = set()
    regressed_designs = set()
    unchanged_designs = set()
    
    comparison_rows = []
    
    # Print which designs were found for debugging
    print(f"Designs in regression output: {sorted(regression_data.keys())}")
    print(f"Designs in baseline: {sorted(baseline_data.keys())}")
    
    for design in regression_data:
        if design not in baseline_data:
            print(f"Warning: Design '{design}' not found in baseline")
            continue
        
        design_has_improvement = False
        design_has_regression = False
        
        for metric_key, metric_name in coverage_metrics:
            try:
                baseline_val = float(baseline_data[design].get(metric_key, 0) or 0)
                new_val = float(regression_data[design].get(metric_key, 0) or 0)
                diff = new_val - baseline_val
                
                # Calculate percentage change
                if baseline_val != 0:
                    pct_change = (diff / baseline_val * 100)
                    pct_change_str = f"{pct_change:+.2f}%"
                elif new_val != 0:
                    # Baseline was 0, but new value is non-zero (infinite improvement)
                    pct_change_str = "N/A (∞)"
                    pct_change = float('inf')  # For comparison purposes
                else:
                    # Both are 0
                    pct_change_str = "0.00%"
                    pct_change = 0
                
                if diff > 0.1:
                    design_has_improvement = True
                elif diff < -0.1:
                    design_has_regression = True
                
                row = [
                    design,
                    metric_name,
                    f"{baseline_val:.2f}",
                    f"{new_val:.2f}",
                    f"{diff:+.2f}",
                    pct_change_str
                ]
                comparison_rows.append(row)
                
            except (ValueError, TypeError) as e:
                print(f"Warning: Could not compare {metric_name} for design '{design}': {e}")
        
        # Determine overall status for this design
        if design_has_improvement and not design_has_regression:
            improved_designs.add(design)
        elif design_has_regression and not design_has_improvement:
            regressed_designs.add(design)
        elif not design_has_improvement and not design_has_regression:
            unchanged_designs.add(design)
        # If both improvement and regression, don't count in any category
    
    # Append comparison report to the same file
    with open(OUTPUT_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        
        # Add separator and comparison section header
        writer.writerow([])
        writer.writerow(['=== COMPARISON WITH BASELINE ==='])
        writer.writerow([])
        
        # Write comparison headers and data
        writer.writerow(comparison_headers)
        for row in comparison_rows:
            writer.writerow(row)
        
        # Add summary statistics at the end
        writer.writerow([])
        writer.writerow(['=== SUMMARY ==='])
        writer.writerow(['Designs improved', len(improved_designs)])
        writer.writerow(['Designs regressed', len(regressed_designs)])
        writer.writerow(['Designs unchanged', len(unchanged_designs)])
        writer.writerow(['Total designs', len(improved_designs) + len(regressed_designs) + len(unchanged_designs)])
    
    print(f"\nComparison report appended to: {OUTPUT_FILE}")


def cleanup_old_csvs():
    """Remove old CSV files from work directory (except baseline and regression_output)."""
    work_path = Path(WORK_DIR)
    if not work_path.exists():
        return
    
    count = 0
    for csv_file in work_path.glob("*.csv"):
        if csv_file.name not in ["regression_output.csv", "baseline.csv"]:
            try:
                csv_file.unlink()
                count += 1
            except Exception as e:
                print(f"Warning: Could not delete {csv_file.name}: {e}")
    
    if count > 0:
        print(f"Cleaned up {count} old CSV file(s) from work directory")


def main():
    """Main entry point for the script."""
    # Check if at least one design has been added
    if not DESIGNS:
        print("Error: No designs specified. Please add at least one design to the DESIGNS list.")
        sys.exit(1)
    
    print(f"Running batch mode with {len(DESIGNS)} design(s): {', '.join(DESIGNS)}")
    
    # Clean up old CSV files before starting
    
    backup_env()
    
    successful_designs = 0
    
    try:
        for design in DESIGNS:
            print(f"\nProcessing design: {design}")
            if run_design(design):
                successful_designs += 1
    finally:
        restore_env()
        print("\nBatch processing complete.")
        print(f"Successfully processed {successful_designs}/{len(DESIGNS)} design(s)")
        
        # Only run CSV operations if at least one design succeeded
        if successful_designs > 0:
            # Extract CSV columns after all designs have been processed
            extract_csv_columns()
            
            # Compare with baseline if it exists
            compare_with_baseline()
        else:
            print("\nNo designs were successfully processed. Skipping CSV operations.")


if __name__ == "__main__":
    main()
