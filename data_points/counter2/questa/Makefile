QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
DATASET_ROOT ?= /mnt/vault0/ehilaneh/llm_verif_dataset/data_points/
BASE_DIR ?= $(DATASET_ROOT)counter2

all: worklib compile sim 

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files and test files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/verif/counter2tb.v $(BASE_DIR)/design/counter2.v 

compile_design:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/design/counter2.v 

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.counter2tb -c -coverage -do "coverage save -onexit counter2_coverage.ucdb; run -all; exit"

clean: 
	rm -rf work transcript counter2.vcd
