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
	$(QUESTA_ROOT)/vlog -sv -cover $(COVERAGE) $(BASE_DIR)/verif/sd_data_serial_host_tb.sv $(BASE_DIR)/design/sd_data_serial_host.v $(BASE_DIR)/design_context/sd_crc_16.v   

compile_design:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -sv -cover $(COVERAGE) $(BASE_DIR)/design/sd_data_serial_host.v $(BASE_DIR)/design_context/sd_crc_16.v   

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.sd_data_serial_host_tb -c -coverage -do "coverage save -onexit SD-card-controller8_coverage.ucdb; run -all; exit"

clean: 
	rm -rf work transcript
