QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
BASE_DIR ?= /mnt/vault0/ehilaneh/hw-for-ml-data/Hand_Data/sha12

all: worklib compile sim 

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/verif/tb_sha1.v $(BASE_DIR)/design/sha1.v $(BASE_DIR)/design_context/sha1_core.v $(BASE_DIR)/design_context/sha1_w_mem.v

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.tb_sha1 -c -coverage -do "coverage save -onexit sha12_coverage.ucdb; run -all; exit"

clean: 
	rm -rf work transcript
