QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
BASE_DIR ?= /mnt/vault0/asbabbit/ml_for_hdl/data_points/agalimberti_NoCRouter_12

all: worklib compile sim

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/src/rtl/noc/noc.sv $(BASE_DIR)/src/if/switch_allocator2crossbar.sv $(BASE_DIR)/src/if/input_block2crossbar.sv $(BASE_DIR)/src/rtl/allocators/switch_allocator.sv $(BASE_DIR)/src/rtl/crossbar/crossbar.sv $(BASE_DIR)/src/rtl/input_port/input_block.sv $(BASE_DIR)/src/rtl/allocators/round_robin_arbiter.sv $(BASE_DIR)/src/rtl/allocators/separable_input_first_allocator.sv $(BASE_DIR)/src/rtl/input_port/rc_unit.sv $(BASE_DIR)/src/rtl/input_port/circular_buffer.sv $(BASE_DIR)/src/rtl/input_port/input_port.sv $(BASE_DIR)/src/rtl/input_port/input_buffer.sv $(BASE_DIR)/src/tb/crossbar/tb_crossbar.sv

sim: 
	echo "simulating test bench and generating .ucdb coverage report"
	$(QUESTA_ROOT)/vsim work.tb_crossbar -c -coverage -do "coverage save -onexit tb_crossbar.ucdb; run -all; exit"

clean: 
	rm -rf work transcript out.vcd

