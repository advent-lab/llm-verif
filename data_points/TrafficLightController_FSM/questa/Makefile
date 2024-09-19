QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
BASE_DIR ?= /mnt/vault0/ehilaneh/hw-for-ml-data/Hand_Data/TrafficLightController1

all: worklib compile sim 

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/verif/FSM_test.v $(BASE_DIR)/design/FSM.v 

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.FSM_test -c -coverage -do "coverage save -onexit TrafficLightController1_coverage.ucdb; run -all; exit"

clean: 
	rm -rf work transcript
