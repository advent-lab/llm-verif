QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
DATASET_ROOT ?= /mnt/vault0/ehilaneh/llm_verif_dataset/data_points/
BASE_DIR ?= $(shell cd .. && pwd)
COVERAGE ?= bcs

all: worklib compile sim 

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files and test bench files"
	$(QUESTA_ROOT)/vlog -sv -cover $(COVERAGE) $(BASE_DIR)/verif/sd_controller_wb_tb.sv $(BASE_DIR)/design/sd_controller_wb.v $(BASE_DIR)/design_context/byte_en_reg.v   

compile_design:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -sv -cover $(COVERAGE) $(BASE_DIR)/design/sd_controller_wb.v $(BASE_DIR)/design_context/byte_en_reg.v   

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.sd_controller_wb_tb -c -coverage -do "coverage save -onexit SD-card-controller6_coverage.ucdb; run -all; exit"

clean: 
	rm -rf work transcript
