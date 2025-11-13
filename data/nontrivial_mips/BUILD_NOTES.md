# NonTrivial MIPS Build Notes

## Status: FAILED - Requires Proprietary IP

This design cannot be included in the verification dataset due to dependencies on proprietary Xilinx IP cores and missing modules.

## Issues Fixed

### 1. Missing Include Directory
**Error:** `Cannot find include file "common_defs.svh"`
**Fix:** Added `+incdir+$(BASE_DIR)/design` to Makefile
**Files Modified:** `questa/Makefile`

### 2. CP0 Forward Module Bug
**Error:** `Could not find field/method name (datareq) in 'pipe_wb'`
**Fix:**
- Changed `datareq` to `cp0_req` in `cpu/exec/cp0_forward.sv` lines 15, 16, 20, 21
- Added `cp0_req_t cp0_req;` field to `pipeline_memwb_t` structure in `cpu/cpu_defs.svh` line 344

**Files Modified:**
- `design/cpu/exec/cp0_forward.sv`
- `design/cpu/cpu_defs.svh`

### 3. Missing Source Directories
**Error:** Failed to open design unit files for cp1, cp2, mmu, bus, interfaces directories
**Fix:** Removed non-existent directories (cp1, cp2, bus, interfaces) from Makefile compilation list. Added existing directories (cpu/regs, cpu/mmu, cpu/*.sv, asic) that were missing.

**Files Modified:** `questa/Makefile`

### 4. Variable Declaration Order
**Error:** `Undefined variable: 'next_offset'` in icache.sv
**Fix:** Moved `next_offset` declaration before the always_comb block that uses it (moved from line 151 to line 142-143)

**Files Modified:** `design/cache/icache.sv`

### 5. SystemVerilog Keyword Conflict
**Error:** `syntax error, unexpected "SystemVerilog keyword 'int'"`
**Fix:** Renamed port `int` to `ext_int` throughout `mycpu_top.v` (lines 9 and 181)

**Files Modified:** `design/mycpu_top.v`

### 6. Testbench Variable Declaration
**Error:** `Undefined variable: 'debug_wb_err'`
**Fix:** Moved `debug_wb_err` declaration before the task that uses it (line 135)

**Files Modified:** `verif/nontrivial_mips_tb.sv`

### 7. Created Simple Testbench
**Reason:** Original testbench required full Loongson SoC wrapper
**Action:** Created `verif/nontrivial_mips_simple_tb.sv` with basic AXI stimulus
**Files Created:**
- `verif/nontrivial_mips_simple_tb.sv`

## Compilation Results

**Design Compilation:** SUCCESS (0 errors, 230 warnings)
**Simulation:** FAILED due to missing proprietary IP

## Blocking Issues (Cannot Be Fixed)

### Missing Xilinx Proprietary IP Cores

The design requires Xilinx XPM (Xilinx Parameterized Macros) memory primitives:
- `xpm_memory_tdpram` - True Dual Port RAM
- `xpm_memory_dpdistram` - Dual Port Distributed RAM

Used in: `design/utils/dual_port_ram.sv`

### Missing FPU IP Cores

The design requires proprietary floating-point IP cores:
- `floating_point_addsub`
- `floating_point_multiply`
- `floating_point_divide`
- `floating_point_sqrt`
- `floating_point_compare`
- `floating_point_int2float`

Used in: `design/cpu/exec/fpu_exec.sv`

### Missing Custom Module

The design requires a custom AXI crossbar module:
- `cpu_internal_crossbar`

Used in: `design/mycpu_top.v` line 294

## Files Modified Summary

1. `questa/Makefile` - Include paths and source files
2. `design/cpu/cpu_defs.svh` - Added cp0_req field to pipeline_memwb_t
3. `design/cpu/exec/cp0_forward.sv` - Fixed field name from datareq to cp0_req
4. `design/cache/icache.sv` - Moved variable declaration
5. `design/mycpu_top.v` - Renamed int to ext_int
6. `verif/nontrivial_mips_tb.sv` - Moved debug_wb_err declaration
7. `verif/nontrivial_mips_simple_tb.sv` - Created new simple testbench

## Recommendation

**Exclude from dataset** due to proprietary IP dependencies. Cannot simulate without:
- Xilinx Vivado XPM library license
- Xilinx Floating Point IP core licenses
- Missing cpu_internal_crossbar module implementation

The design compiles successfully but cannot be simulated or verified without these commercial components.
