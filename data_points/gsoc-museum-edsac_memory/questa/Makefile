QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
DATASET_ROOT ?= /mnt/vault0/ehilaneh/llm_verif_dataset/data_points/
BASE_DIR ?= $(DATASET_ROOT)gsoc-museum-edsac_memory

all: worklib compile sim

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files and test files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/test/edsac/memory/memory_tb.v $(BASE_DIR)/src/edsac/memory/memory.v $(BASE_DIR)/src/edsac/memory/delay_line.v

compile_design:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/src/edsac/memory/memory.v $(BASE_DIR)/src/edsac/memory/delay_line.v

sim: 
	echo "simulating test bench and generating .ucdb coverage report"
	$(QUESTA_ROOT)/vsim work.memory_tb -c -coverage -do "coverage save -onexit memory_tb.ucdb; run -all; exit"

clean: 
	rm -rf work transcript memory.vcd
