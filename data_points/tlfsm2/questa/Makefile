QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
BASE_DIR ?= /mnt/vault0/ehilaneh/hw-for-ml-data/Hand_Data/tlfsm2

all: worklib compile sim 

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/verif/tlfsm2tb.v $(BASE_DIR)/design/tlfsm2.v  $(BASE_DIR)/design_context/counter2.v $(BASE_DIR)/design_context/cntclk2.v

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.tlfsm2tb -c -coverage -do "coverage save -onexit tlfsm2_coverage.ucdb; run -all; exit"

clean: 
	rm -rf work transcript tlfsm2.vcd
