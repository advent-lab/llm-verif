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
	$(QUESTA_ROOT)/vlog -sv -cover s $(BASE_DIR)/src/rtl/noc/noc.sv $(BASE_DIR)/src/rtl/input_port/circular_buffer.sv $(BASE_DIR)/src/tb/input_port/tb_circular_buffer.sv

compile_design: 
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -sv -cover s $(BASE_DIR)/src/rtl/noc/noc.sv $(BASE_DIR)/src/rtl/input_port/circular_buffer.sv 

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.tb_circular_buffer -c -coverage -do "coverage exclude tb_circular_coverage; coverage save -onexit tb_circular_buffer.ucdb; run -all; exit"

clean: 
	rm -rf work transcript out.vcd
