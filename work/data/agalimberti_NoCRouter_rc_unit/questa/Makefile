QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
DATASET_ROOT ?= /mnt/vault0/ehilaneh/llm_verif_dataset/data_points/
BASE_DIR ?= $(DATASET_ROOT)agalimberti_NoCRouter_rc_unit

all: worklib compile sim

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files and test files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/src/rtl/noc/noc.sv $(BASE_DIR)/src/rtl/input_port/rc_unit.sv $(BASE_DIR)/src/tb/input_port/tb_rc_unit.sv

compile_design:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/src/rtl/noc/noc.sv $(BASE_DIR)/src/rtl/input_port/rc_unit.sv 

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.tb_rc_unit -coverage -c -do "coverage save -onexit tb_rc_unit.ucdb; run -all; exit"

clean: 
	rm -rf work transcript out.vcd
