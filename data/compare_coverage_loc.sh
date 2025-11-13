#!/usr/bin/env bash
# Compare QuestaSim coverage bins to Lines of Code for each design
# This script analyzes coverage density relative to design complexity
#
# Usage: ./compare_coverage_loc.sh [directory]
#   If no directory specified, searches common locations for coverage.ucdb files

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Base directory - can be overridden by command line argument
if [ $# -gt 0 ]; then
    base_dir="$1"
else
    # Default: search current directory and common subdirectories
    base_dir="."
fi

# Function to extract total bins from coverage.ucdb
get_coverage_bins() {
    local ucdb_file="$1"
    if [ ! -f "$ucdb_file" ]; then
        echo "0"
        return
    fi

    # Use vcover to get summary and extract total bins from Statements line
    vcover report -summary "$ucdb_file" 2>/dev/null | \
        awk '/^    Statements/ {print $2; exit}'
}

# Function to get coverage percentage
get_coverage_percent() {
    local ucdb_file="$1"
    if [ ! -f "$ucdb_file" ]; then
        echo "0.00"
        return
    fi

    vcover report -summary "$ucdb_file" 2>/dev/null | \
        awk '/^    Statements/ {gsub(/%/,"",$NF); print $NF; exit}'
}

# Function to get hits and misses
get_coverage_details() {
    local ucdb_file="$1"
    if [ ! -f "$ucdb_file" ]; then
        echo "0 0"
        return
    fi

    vcover report -summary "$ucdb_file" 2>/dev/null | \
        awk '/^    Statements/ {print $3, $4; exit}'
}

# Function to count LOC (code-only) for Verilog/SystemVerilog
count_loc() {
    if ! command -v cloc >/dev/null 2>&1; then
        echo "0"
        return
    fi

    cloc --csv --quiet --include-lang=Verilog-SystemVerilog "$@" 2>/dev/null \
        | awk -F, 'NR>2 && $2!="SUM"{code+=$5} END{print (code?code:0)}'
}

# Print header
printf "%-28s %8s %8s %10s %10s %10s %12s %12s\n" \
    "Design" "LOC" "Bins" "Hits" "Misses" "Cov%" "Bins/LOC" "LOC/Bin"
printf "%-28s %8s %8s %10s %10s %10s %12s %12s\n" \
    "------" "---" "----" "----" "------" "----" "--------" "-------"

# Track totals
total_loc=0
total_bins=0
total_hits=0
total_misses=0
design_count=0

# Find all directories with .ucdb files
while IFS= read -r -d '' ucdb_file; do
    dir=$(dirname "$ucdb_file")
    # Get design name from parent directory (go up from questa/)
    if [[ "$dir" == */questa ]]; then
        design_dir=$(dirname "$dir")
        base=$(basename "$design_dir")
    else
        base=$(basename "$dir")
    fi

    # Get coverage metrics
    bins=$(get_coverage_bins "$ucdb_file")
    coverage_pct=$(get_coverage_percent "$ucdb_file")
    read hits misses < <(get_coverage_details "$ucdb_file")

    # Get LOC metrics
    primary_count=0
    context_count=0

    # If in questa/, go up to design directory
    if [[ "$dir" == */questa ]]; then
        search_dir=$(dirname "$dir")
    else
        search_dir="$dir"
    fi

    # Try different directory structures
    if [ -d "$search_dir/design" ] && find "$search_dir/design" -type f \( -name '*.v' -o -name '*.sv' \) -print -quit 2>/dev/null | grep -q .; then
        primary_count=$(count_loc "$search_dir/design")
        if [ -d "$search_dir/design_context" ] && find "$search_dir/design_context" -type f \( -name '*.v' -o -name '*.sv' \) -print -quit 2>/dev/null | grep -q .; then
            context_count=$(count_loc "$search_dir/design_context")
        fi
    elif [ -d "$search_dir/rtl" ] && find "$search_dir/rtl" -type f \( -name '*.v' -o -name '*.sv' \) -print -quit 2>/dev/null | grep -q .; then
        primary_count=$(count_loc "$search_dir/rtl")
    elif [ -d "$search_dir/src/rtl" ] && find "$search_dir/src/rtl" -type f \( -name '*.v' -o -name '*.sv' \) -print -quit 2>/dev/null | grep -q .; then
        primary_count=$(count_loc "$search_dir/src/rtl")
    elif [ -d "$search_dir/src" ] && find "$search_dir/src" -type f \( -name '*.v' -o -name '*.sv' \) -print -quit 2>/dev/null | grep -q .; then
        primary_count=$(count_loc "$search_dir/src")
    fi

    loc=$(( primary_count + context_count ))

    # Calculate metrics
    if [ "$loc" -gt 0 ] && [ "$bins" -gt 0 ]; then
        bins_per_loc=$(echo "scale=4; $bins / $loc" | bc)
        loc_per_bin=$(echo "scale=2; $loc / $bins" | bc)
    else
        bins_per_loc="N/A"
        loc_per_bin="N/A"
    fi

    # Print row
    printf "%-28s %8d %8d %10d %10d %9s%% %12s %12s\n" \
        "$base" "$loc" "$bins" "$hits" "$misses" "$coverage_pct" "$bins_per_loc" "$loc_per_bin"

    # Update totals
    total_loc=$((total_loc + loc))
    total_bins=$((total_bins + bins))
    total_hits=$((total_hits + hits))
    total_misses=$((total_misses + misses))
    design_count=$((design_count + 1))

done < <(find "$base_dir" -maxdepth 3 -name "*.ucdb" -print0 2>/dev/null)

# Print totals if any designs found
if [ "$design_count" -gt 0 ]; then
    printf "%-28s %8s %8s %10s %10s %10s %12s %12s\n" \
        "------" "---" "----" "----" "------" "----" "--------" "-------"

    if [ "$total_loc" -gt 0 ] && [ "$total_bins" -gt 0 ]; then
        total_cov_pct=$(echo "scale=2; 100 * $total_hits / $total_bins" | bc)
        total_bins_per_loc=$(echo "scale=4; $total_bins / $total_loc" | bc)
        total_loc_per_bin=$(echo "scale=2; $total_loc / $total_bins" | bc)
    else
        total_cov_pct="0.00"
        total_bins_per_loc="N/A"
        total_loc_per_bin="N/A"
    fi

    printf "%-28s %8d %8d %10d %10d %9s%% %12s %12s\n" \
        "TOTAL ($design_count designs)" "$total_loc" "$total_bins" "$total_hits" "$total_misses" \
        "$total_cov_pct" "$total_bins_per_loc" "$total_loc_per_bin"

    echo ""
    echo "Metrics explanation:"
    echo "  LOC        = Lines of code (excluding comments/blanks)"
    echo "  Bins       = Total coverage bins (statements)"
    echo "  Hits       = Bins that were exercised"
    echo "  Misses     = Bins that were not exercised"
    echo "  Cov%       = Coverage percentage (Hits/Bins)"
    echo "  Bins/LOC   = Coverage bin density (higher = more granular coverage)"
    echo "  LOC/Bin    = Lines per coverage bin (lower = more granular coverage)"
fi
