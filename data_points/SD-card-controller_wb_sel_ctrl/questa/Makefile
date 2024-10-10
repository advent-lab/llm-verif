QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
DATASET_ROOT ?= /mnt/vault0/ehilaneh/llm_verif_dataset/data_points/
BASE_DIR ?= $(DATASET_ROOT)SD-card-controller_wb_sel_ctrl

all: worklib compile sim 

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files and test bench files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/verif/sd_wb_sel_ctrl_tb.sv $(BASE_DIR)/design/sd_wb_sel_ctrl.v   

compile_design:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/design/sd_wb_sel_ctrl.v   

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.sd_wb_sel_ctrl_tb -c -coverage -do "coverage save -onexit SD-card-controller11_coverage.ucdb; run -all; exit"

clean: 
	rm -rf work transcript
