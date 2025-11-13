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
	$(QUESTA_ROOT)/vlog -sv -cover $(COVERAGE) $(BASE_DIR)/tb_llm_lab4-fitbit_tracker_22.v $(BASE_DIR)/design_context/Rotator.v $(BASE_DIR)/design_context/debouncer.v $(BASE_DIR)/design_context/pulse_generator.v $(BASE_DIR)/design_context/bin2bcd_fsm.v $(BASE_DIR)/design_context/fitbit_tracker.v $(BASE_DIR)/design_context/four_digit_display.v $(BASE_DIR)/design_context/top.v 

compile_design:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -sv -cover $(COVERAGE) $(BASE_DIR)/design_context/Rotator.v $(BASE_DIR)/design_context/debouncer.v $(BASE_DIR)/design_context/pulse_generator.v $(BASE_DIR)/design_context/bin2bcd_fsm.v $(BASE_DIR)/design_context/fitbit_tracker.v $(BASE_DIR)/design_context/four_digit_display.v $(BASE_DIR)/design_context/top.v 

sim:
	echo "simulating test bench and generating .ucdb coverage report"
	$(QUESTA_ROOT)/vsim work.tb_top_module -c -coverage -do "coverage save -onexit lab4_fitbit_tracker_coverage.ucdb; run -all; exit"

clean:
	rm -rf work transcript
