QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
DATASET_ROOT ?= /mnt/vault0/ehilaneh/llm_verif_dataset/data_points/
BASE_DIR ?= $(shell cd .. && pwd)
COVERAGE ?= bcs

all: worklib compile sim

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files and test files"
	$(QUESTA_ROOT)/vlog -sv -cover $(COVERAGE) $(BASE_DIR)/src/tb/allocators/tb_separable_input_first_allocator.sv $(BASE_DIR)/src/rtl/allocators/separable_input_first_allocator.sv $(BASE_DIR)/src/rtl/allocators/round_robin_arbiter.sv

compile_design:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -sv -cover $(COVERAGE) $(BASE_DIR)/src/rtl/allocators/separable_input_first_allocator.sv $(BASE_DIR)/src/rtl/allocators/round_robin_arbiter.sv

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.tb_separable_input_first_allocator -c -coverage -do "coverage save -onexit tb_separable_input_first_allocator.ucdb; run -all; exit"

clean: 
	rm -rf work transcript out.vcd
