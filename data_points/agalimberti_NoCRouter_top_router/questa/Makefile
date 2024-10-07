QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
DATASET_ROOT ?= /mnt/vault0/ehilaneh/llm_verif_dataset/data_points/
BASE_DIR ?= $(DATASET_ROOT)agalimberti_NoCRouter_top_router/src

all: worklib compile sim

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files and test files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/rtl/noc/noc.sv $(BASE_DIR)/tb/router/tb_all_modules.sv $(BASE_DIR)/rtl/router/router.sv $(BASE_DIR)/if/input_block2crossbar.sv $(BASE_DIR)/if/input_block2switch_allocator.sv $(BASE_DIR)/if/input_block2vc_allocator.sv $(BASE_DIR)/if/router2router.sv $(BASE_DIR)/if/switch_allocator2crossbar.sv $(BASE_DIR)/rtl/input_port/circular_buffer.sv $(BASE_DIR)/rtl/input_port/input_block.sv $(BASE_DIR)/rtl/input_port/input_buffer.sv $(BASE_DIR)/rtl/input_port/input_port.sv $(BASE_DIR)/rtl/input_port/rc_unit.sv $(BASE_DIR)/rtl/crossbar/crossbar.sv $(BASE_DIR)/rtl/allocators/round_robin_arbiter.sv $(BASE_DIR)/rtl/allocators/separable_input_first_allocator.sv $(BASE_DIR)/rtl/allocators/switch_allocator.sv $(BASE_DIR)/rtl/allocators/vc_allocator.sv

compile_design:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/rtl/noc/noc.sv $(BASE_DIR)/rtl/router/router.sv $(BASE_DIR)/if/input_block2crossbar.sv $(BASE_DIR)/if/input_block2switch_allocator.sv $(BASE_DIR)/if/input_block2vc_allocator.sv $(BASE_DIR)/if/router2router.sv $(BASE_DIR)/if/switch_allocator2crossbar.sv $(BASE_DIR)/rtl/input_port/circular_buffer.sv $(BASE_DIR)/rtl/input_port/input_block.sv $(BASE_DIR)/rtl/input_port/input_buffer.sv $(BASE_DIR)/rtl/input_port/input_port.sv $(BASE_DIR)/rtl/input_port/rc_unit.sv $(BASE_DIR)/rtl/crossbar/crossbar.sv $(BASE_DIR)/rtl/allocators/round_robin_arbiter.sv $(BASE_DIR)/rtl/allocators/separable_input_first_allocator.sv $(BASE_DIR)/rtl/allocators/switch_allocator.sv $(BASE_DIR)/rtl/allocators/vc_allocator.sv

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.tb_all_modules -c -coverage -do "coverage save -onexit tb_all_modules.ucdb; run -all; exit"

clean: 
	rm -rf work transcript out.vcd
