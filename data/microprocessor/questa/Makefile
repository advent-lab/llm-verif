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
	$(QUESTA_ROOT)/vlog -sv -cover $(COVERAGE) $(BASE_DIR)/verif/top.sv $(BASE_DIR)/verif/testbench.sv $(BASE_DIR)/design/alu.sv $(BASE_DIR)/design/comparator_signed.sv $(BASE_DIR)/design/ifc_dec_rf.sv $(BASE_DIR)/design/ifc_rob_alu.sv $(BASE_DIR)/design/ifc_rob_dec.sv $(BASE_DIR)/design/ifc_rob_lsq.sv $(BASE_DIR)/design/ifc_rob_rf.sv $(BASE_DIR)/design/ifc_test.sv $(BASE_DIR)/design/ins_parse.sv $(BASE_DIR)/design/insdec.sv $(BASE_DIR)/design/lsq.sv $(BASE_DIR)/design/regfile.sv $(BASE_DIR)/design/rob.sv $(BASE_DIR)/design/superscalar.sv $(BASE_DIR)/design/timescale.sv

compile_design:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -sv -cover $(COVERAGE) $(BASE_DIR)/design/alu.sv $(BASE_DIR)/design/comparator_signed.sv $(BASE_DIR)/design/ifc_dec_rf.sv $(BASE_DIR)/design/ifc_rob_alu.sv $(BASE_DIR)/design/ifc_rob_dec.sv $(BASE_DIR)/design/ifc_rob_lsq.sv $(BASE_DIR)/design/ifc_rob_rf.sv $(BASE_DIR)/design/ifc_test.sv $(BASE_DIR)/design/ins_parse.sv $(BASE_DIR)/design/insdec.sv $(BASE_DIR)/design/lsq.sv $(BASE_DIR)/design/regfile.sv $(BASE_DIR)/design/rob.sv $(BASE_DIR)/design/superscalar.sv $(BASE_DIR)/design/timescale.sv

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.top -c -coverage -do "coverage save -onexit microprocessor_coverage.ucdb; run -all; exit"

clean: 
	rm -rf work transcript 
