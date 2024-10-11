QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
DATASET_ROOT ?= /mnt/vault0/ehilaneh/llm_verif_dataset/data_points/
BASE_DIR ?= $(DATASET_ROOT)fifo

all: worklib compile sim

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files and test files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/verif/testbench.sv $(BASE_DIR)/design/sync_fifo.sv

compile_design:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/design/sync_fifo.sv

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.test_v2 -c -coverage -do "coverage save -onexit fifo_coverage.ucdb; run -all; exit"

clean: 
	rm -rf work transcript dump.vcd
