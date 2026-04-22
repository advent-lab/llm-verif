#!/bin/bash

test_name="rgb_color_space_hsv_test"    # uvm_test class
top_mod="rgb_color_space_hsv_Top"          # top module name
seed=$RANDOM

# ── 1. Create work library (one-time, like VCS's csrc) ──
vlib work

# ── 2. Compile (replaces vlogan + vcs elaborate) ──
# Compile — needs -L uvm to pull in the built-in
vlog -sv -mfcu -f ../testbench/rgb_color_space_hsv_list.f \
    +incdir+$UVM_HOME/src -L uvm -l compile.log

# Optimize — UVM is already in work, no -L needed
vopt +acc rgb_color_space_hsv_Top -o opt_top \
    +cover=bcestf -l optimize.log

# Simulate — no -L needed either
vsim -c opt_top -coverage -sv_seed $seed \
    -sv_lib /opt/siemens/questasim/uvm-1.2/linux_x86_64/uvm_dpi \
    +UVM_TESTNAME=rgb_color_space_hsv_test +UVM_VERBOSITY=UVM_HIGH \
    -do "coverage save -onexit coverage/cov.ucdb; run -all; quit" \
    -l simv.log

if [ $? -ne 0 ]; then exit 1; fi
