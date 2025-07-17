QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
DATASET_ROOT ?= /mnt/vault0/ehilaneh/llm_verif_dataset/data_points/
BASE_DIR ?= $(DATASET_ROOT)mkmif_core

all: worklib compile sim 

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files and test files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/verif/tb_mkmif_core.v $(BASE_DIR)/design/mkmif_core.v $(BASE_DIR)/design_context/mkmif_spi.v   

compile_design:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/design/mkmif_core.v $(BASE_DIR)/design_context/mkmif_spi.v   

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.tb_mkmif_core -c -coverage -do "coverage save -onexit mkmif1_coverage.ucdb; run -all; exit"

clean: 
	rm -rf work transcript
