#!/usr/bin/env bash
# Summarize Verilog/SystemVerilog LOC (excluding comments/blank) per top-level design
# Requires: cloc (https://github.com/AlDanial/cloc)

set -euo pipefail

# Set this to your base directory containing the design folders (e.g., sha1_top/, chacha_top/, etc.)
base_dir="./llm_verif_dataset/data"  # <-- change if needed, e.g., base_dir="/home/sean/llm_verif/dataset"

if ! command -v cloc >/dev/null 2>&1; then
  echo "Error: cloc is not installed. Install it (e.g., 'sudo apt-get install cloc' or 'brew install cloc')." >&2
  exit 1
fi

# Count LOC (code-only) for Verilog/SystemVerilog within given paths
count_loc() {
  # cloc CSV columns: files,language,blank,comment,code
  cloc --csv --quiet --include-lang=Verilog-SystemVerilog "$@" 2>/dev/null \
    | awk -F, 'NR>2 && $2!="SUM"{code+=$5} END{print (code?code:0)}'
}

printf "%-28s %12s %16s %14s\n" "Directory" "primary(code)" "context(code)" "TOTAL(code)"
printf "%-28s %12s %16s %14s\n" "---------" "--------------" "--------------" "-----------"

# Enumerate top-level directories
while IFS= read -r -d '' dir; do
  base="$(basename "$dir")"

  primary_count=0
  context_count=0

  # Try different directory structures
  # Structure 1: design/ and design_context/
  if [ -d "$dir/design" ] && find "$dir/design" -type f \( -name '*.v' -o -name '*.sv' \) -print -quit 2>/dev/null | grep -q .; then
    primary_count=$(count_loc "$dir/design")
    if [ -d "$dir/design_context" ] && find "$dir/design_context" -type f \( -name '*.v' -o -name '*.sv' \) -print -quit 2>/dev/null | grep -q .; then
      context_count=$(count_loc "$dir/design_context")
    fi
  # Structure 2: rtl/ (like cvdp_agentic_*)
  elif [ -d "$dir/rtl" ] && find "$dir/rtl" -type f \( -name '*.v' -o -name '*.sv' \) -print -quit 2>/dev/null | grep -q .; then
    primary_count=$(count_loc "$dir/rtl")
  # Structure 3: src/ (like agalimberti_*)
  elif [ -d "$dir/src" ] && find "$dir/src" -type f \( -name '*.v' -o -name '*.sv' \) -print -quit 2>/dev/null | grep -q .; then
    primary_count=$(count_loc "$dir/src")
  fi

  total=$(( primary_count + context_count ))

  if [ "$total" -gt 0 ]; then
    printf "%-28s %12d %16d %14d\n" "$base" "$primary_count" "$context_count" "$total"
  fi
done < <(find "$base_dir" -maxdepth 1 -mindepth 1 -type d -print0)

