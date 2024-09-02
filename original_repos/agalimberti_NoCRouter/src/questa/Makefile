QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
BASE_DIR ?= /mnt/vault0/asbabbit/ml_for_hdl/kept_repos/agalimberti_NoCRouter/src

all: worklib compile sim 

bench: allocators crossbar input_port mesh router

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

allocators: round_robin separable_input switch_allocator vc_allocator

round_robin:
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/tb/allocators/tb_round_robin_arbiter.sv $(BASE_DIR)/rtl/allocators/round_robin_arbiter.sv 
	$(QUESTA_ROOT)/vsim work.tb_round_robin_arbiter -c -coverage -do "coverage save -onexit round_robin_arbiter_coverage.ucdb; run -all; exit"

separable_input:
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/tb/allocators/tb_separable_input_first_allocator.sv $(BASE_DIR)/rtl/allocators/separable_input_first_allocator.sv  $(BASE_DIR)/rtl/allocators/round_robin_arbiter.sv
	$(QUESTA_ROOT)/vsim work.tb_separable_input_first_allocator -c -coverage -do "coverage save -onexit separable_input_coverage.ucdb; run -all; exit"

switch_allocator:

vc_allocator: 

clean: 
	rm -rf work transcript out.vcd
