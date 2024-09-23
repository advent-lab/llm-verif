QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
BASE_DIR ?= /mnt/vault0/ehilaneh/hw-for-ml-data/Hand_Data/trng2

all: worklib compile sim 

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/verif/tb_mixer.v $(BASE_DIR)/design/trng_mixer.v $(BASE_DIR)/design_context/sha512.v $(BASE_DIR)/design_context/sha512_core.v $(BASE_DIR)/design_context/sha512_h_constants.v $(BASE_DIR)/design_context/sha512_k_constants.v $(BASE_DIR)/design_context/sha512_w_mem.v

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.tb_mixer -c -coverage -do "coverage save -onexit trng2_coverage.ucdb; run -all; exit"

clean: 
	rm -rf work transcript
