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
	$(QUESTA_ROOT)/vlog -sv -cover $(COVERAGE) $(BASE_DIR)/verif/tb_chacha.v $(BASE_DIR)/design/chacha.v $(BASE_DIR)/design_context/chacha_core.v $(BASE_DIR)/design_context/chacha_qr.v   

compile_design: 
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -sv -cover $(COVERAGE) $(BASE_DIR)/design/chacha.v $(BASE_DIR)/design_context/chacha_core.v $(BASE_DIR)/design_context/chacha_qr.v   

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.tb_chacha -c -coverage -do "coverage save -onexit chacha0_coverage.ucdb; run -all; exit"

clean: 
	rm -rf work transcript
