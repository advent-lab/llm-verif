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
	$(QUESTA_ROOT)/vlog -sv -cover $(COVERAGE) $(BASE_DIR)/verif/poly_filter_tb.sv $(BASE_DIR)/rtl/poly_filter.sv $(BASE_DIR)/rtl/adder_tree.sv $(BASE_DIR)/rtl/coeff_ram.sv $(BASE_DIR)/rtl/shift_register.sv

compile_design:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -sv -cover $(COVERAGE) $(BASE_DIR)/rtl/poly_filter.sv $(BASE_DIR)/rtl/adder_tree.sv $(BASE_DIR)/rtl/coeff_ram.sv $(BASE_DIR)/rtl/shift_register.sv

sim:
	echo "simulating test bench and generating .ucdb coverage report"
	$(QUESTA_ROOT)/vsim work.poly_filter_tb -c -coverage -do "coverage save -onexit poly_filter_coverage.ucdb; run -all; exit"

clean:
	rm -rf work transcript
