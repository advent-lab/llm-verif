QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
DATASET_ROOT ?= /mnt/vault0/ehilaneh/llm_verif_dataset/data_points/
BASE_DIR ?= $(DATASET_ROOT)TrafficLightController_Main

all: worklib compile sim 

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files and test bench files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/verif/TrafficControllerMain_test.v $(BASE_DIR)/design/TrafficControllerMain.v $(BASE_DIR)/design_context/Divider.v $(BASE_DIR)/design_context/FSM.v $(BASE_DIR)/design_context/Synchronizer.v $(BASE_DIR)/design_context/TimeParameter.v $(BASE_DIR)/design_context/Timer.v $(BASE_DIR)/design_context/WalkRegister.v 

compile_design:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/design/TrafficControllerMain.v $(BASE_DIR)/design_context/Divider.v $(BASE_DIR)/design_context/FSM.v $(BASE_DIR)/design_context/Synchronizer.v $(BASE_DIR)/design_context/TimeParameter.v $(BASE_DIR)/design_context/Timer.v $(BASE_DIR)/design_context/WalkRegister.v 

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.TrafficControllerMain_test -c -coverage -do "coverage save -onexit TrafficLightController5_coverage.ucdb; run -all; exit"

clean: 
	rm -rf work transcript
