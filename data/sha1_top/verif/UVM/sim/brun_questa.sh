#!/bin/bash
test_name="sha1_test"
top_mod="sha1_Top"
seed=$RANDOM

# ── 1. Create work library ──
vlib work

# ── 2. Remap mtiUvm to the pre-compiled UVM 1.2 library ──
vmap mtiUvm /opt/siemens/questasim/uvm-1.2

# ── 3. Compile — use -L uvm_1_2 to pick up the 1.2 built-in ──
vlog -sv -mfcu -f ../testbench/sha1_list.f \
    +incdir+/opt/siemens/questasim/verilog_src/uvm-1.2/src \
    -L /opt/siemens/questasim/uvm-1.2 \
    -l compile.log

# ── 4. Optimize — pass the same -L so vopt sees the UVM library ──
vopt +acc $top_mod -o opt_top \
    +cover=bcestf \
    -L /opt/siemens/questasim/uvm-1.2 \
    -l optimize.log

# ── 5. Simulate ──
mkdir -p coverage
vsim -c opt_top -coverage -sv_seed $seed \
    -sv_lib /opt/siemens/questasim/uvm-1.2/linux_x86_64/uvm_dpi \
    "+UVM_TESTNAME=$test_name" "+UVM_VERBOSITY=UVM_HIGH" \
    -do "coverage save -onexit coverage/cov.ucdb; run -all; quit" \
    -l simv.log

if [ $? -ne 0 ]; then exit 1; fi
