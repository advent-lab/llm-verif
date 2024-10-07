QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
DATASET_ROOT ?= /mnt/vault0/ehilaneh/llm_verif_dataset/data_points/
BASE_DIR ?= $(DATASET_ROOT)onehzclk

all: worklib compile sim 

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files and test bench files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/verif/onehzclktb.v $(BASE_DIR)/design/onehzclk.v  $(BASE_DIR)/design_context/counter.v $(BASE_DIR)/design_context/cntclk.v

compile_design:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/design/onehzclk.v  $(BASE_DIR)/design_context/counter.v $(BASE_DIR)/design_context/cntclk.v

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.onehzclktb -c -coverage -do "coverage save -onexit onehzclk_coverage.ucdb; run -all; exit"

clean: 
	rm -rf work transcript onehzclk.vcd
