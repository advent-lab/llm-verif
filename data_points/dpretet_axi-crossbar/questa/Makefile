QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
BASE_DIR ?= /mnt/vault0/asbabbit/ml_for_hdl/llm_verif_dataset/data_points
PROJECT_DIR ?= $(BASE_DIR)/dpretet_axi-crossbar
PROJECT_FILES ?=  $(PROJECT_DIR)/rtl/axicb_crossbar_lite_top.sv $(PROJECT_DIR)/rtl/axicb_crossbar_top.sv $(PROJECT_DIR)/rtl/axicb_round_robin.sv $(PROJECT_DIR)/rtl/axicb_checker.sv $(PROJECT_DIR)/rtl/axicb_switch_top.sv $(PROJECT_DIR)/rtl/axicb_mst_if.sv $(PROJECT_DIR)/rtl/axicb_pipeline.sv $(PROJECT_DIR)/rtl/axicb_slv_if.sv $(PROJECT_DIR)/rtl/axicb_scfifo_ram.sv $(PROJECT_DIR)/rtl/axicb_scfifo.sv $(PROJECT_DIR)/rtl/axicb_round_robin_core.sv $(PROJECT_DIR)/rtl/axicb_slv_switch.sv $(PROJECT_DIR)/rtl/axicb_mst_switch.sv

all: worklib compile sim

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs $(PROJECT_FILES)

sim: 
	echo "simulating test bench and generating .ucdb coverage report"
	$(QUESTA_ROOT)/vsim work.axicb_crossbar_lite_top -c -coverage -do "coverage save -onexit axicb_crossbar_lite_top.ucdb; run -all; exit"

clean: 
	rm -rf work transcript
