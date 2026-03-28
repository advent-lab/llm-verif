# Adding an OpenTitan Design to the llm-verif Dataset

## Prerequisites

- The design must have a successful build in `opentitan/build/ip_manifest_batch/<ip_name>/`
- QuestaSim available (set `COMPILER` in `.env`)

## Steps

### 1. Identify the IP and its build artifacts

Find the IP in `opentitan/build/ip_manifest_batch/`. Key files:
- `meta/compiled_files_in_order.txt` — the ordered dependency list (your source of truth)
- `work/src/` — all source files organized by module

### 2. Create the data directory

```
mkdir -p data/ot_<ip_name>/rtl data/ot_<ip_name>/deps data/ot_<ip_name>/doc
```

### 3. Copy RTL files

Copy the IP's own RTL from `work/src/lowrisc_ip_<ip_name>_*/rtl/` into `data/ot_<ip_name>/rtl/`.

### 4. Copy dependency files

Copy all other files from `work/src/` (everything except the IP's own RTL) into `data/ot_<ip_name>/deps/`. Flatten the directory structure — all deps go into a single `deps/` folder.

### 5. Replace technology-specific primitives with generic versions

**This is the most common source of errors.** The build may pick ASAP7 or Xilinx tech-mapped primitives. These must be replaced with generic (behavioral) implementations:

| Tech-specific file | Generic replacement source |
|---|---|
| `prim_flop_en.sv` (ASAP7: uses `DFFASRHQNx1_ASAP7_75t_R`) | `opentitan/hw/ip/prim_generic/rtl/prim_flop_en.sv` |
| `prim_flop_no_rst.sv` (ASAP7: uses `DFFHQNx1_ASAP7_75t_R`) | `opentitan/hw/ip/prim_generic/rtl/prim_flop_no_rst.sv` |
| `prim_xilinx_rom.sv` (Xilinx: uses `xpm_memory_sprom`) | `opentitan/hw/ip/prim_generic/rtl/prim_rom.sv` |

**How to detect:** Look for `_asap7_` or `_xilinx_` in the directory names under `work/src/`. If `lowrisc_prim_asap7_*` or `lowrisc_prim_xilinx_*` directories exist, the files from those directories need generic replacements.

You can find generic versions at `opentitan/hw/ip/prim_generic/rtl/` or copy from a known-working design's `deps/` (e.g., `data/ot_adc_ctrl/deps/`).

IMPORTANT: Notify the user about any changes you make to the rtl files, as this may affect the design's behavior and the test results.

### 6. Copy documentation

Copy spec/docs from the IP's source at `opentitan/hw/ip/<ip_name>/doc/` into `data/ot_<ip_name>/doc/`.

### 7. Add to dashboard.json

Add a new entry following this template:

```json
"ot_<ip_name>": {
    "design": [
        "$(BASE_DIR)/ot_<ip_name>/rtl/<top_module>.sv"
    ],
    "design_context": [
        "$(BASE_DIR)/ot_<ip_name>/rtl/<other_rtl_files>.sv"
    ],
    "compile_deps": [
        "$(BASE_DIR)/ot_<ip_name>/deps/<dep1_pkg>.sv",
        ...
    ],
    "spec": [
        "$(BASE_DIR)/ot_<ip_name>/doc/specification.md"
    ]
}
```

**Critical: compile_deps ordering.** The files in `compile_deps` must follow the order from `compiled_files_in_order.txt`. Packages must come before the modules that import them. Common ordering pitfalls:

- IP-specific state packages (e.g., `lc_ctrl_state_pkg`) must come before the main IP package (`lc_ctrl_pkg`)
- The main IP package must come before any external packages that depend on it (e.g., `lc_ctrl_pkg` before `otp_ctrl_pkg`)
- All packages must come before modules that use them (e.g., `lc_ctrl_pkg` before `tlul_lc_gate.sv`)

**Tip:** Packages from `rtl/` can be listed in `compile_deps` (with the `rtl/` path) if they are needed by dependency modules. They don't have to stay in `design_context`.

### 8. Validate

```bash
source .venv/bin/activate
python scripts/test_design.py ot_<ip_name>
```

Expected output: `DESIGN 'ot_<ip_name>' IS READY FOR FRAMEWORK INGESTION`

### Common errors and fixes

| Error | Cause | Fix |
|---|---|---|
| `Module 'DFFASRHQNx1_ASAP7_75t_R' is not defined` | ASAP7 tech primitive in deps | Replace with generic `prim_flop_en.sv` |
| `Module 'xpm_memory_sprom' is not defined` | Xilinx tech primitive in deps | Replace with generic `prim_rom.sv` |
| `Could not find the package (X)` | Missing or misordered package | Add package to compile_deps before its consumers |
| `Class or package 'X' not found` | Package compiled after the module that uses it | Reorder compile_deps per `compiled_files_in_order.txt` |
