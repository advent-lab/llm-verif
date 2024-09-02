QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
BASE_DIR ?= /mnt/vault0/asbabbit/ml_for_hdl/data_points/agalimberti_NoCRouter_6/src

all: worklib compile sim

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/rtl/noc/noc.sv $(BASE_DIR)/tb/allocators/tb_switch_allocator.sv $(BASE_DIR)/rtl/allocators/switch_allocator.sv $(BASE_DIR)/rtl/allocators/separable_input_first_allocator.sv $(BASE_DIR)/rtl/allocators/round_robin_arbiter.sv $(BASE_DIR)/if/switch_allocator2crossbar.sv $(BASE_DIR)/if/input_block2switch_allocator.sv

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.tb_switch_allocator -c -coverage -do "coverage save -onexit tb_switch_allocator.ucdb; run -all; exit"

clean: 
	rm -rf work transcript out.vcd
