QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
BASE_DIR ?= /mnt/vault0/ehilaneh/hw-for-ml-data/Hand_Data/trng1

all: worklib compile sim 

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/verif/tb_csprng.v $(BASE_DIR)/design/trng_csprng.v $(BASE_DIR)/design_context/chacha.v $(BASE_DIR)/design_context/chacha_core.v $(BASE_DIR)/design_context/chacha_qr.v $(BASE_DIR)/design_context/trng_csprng_fifo.v 

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.tb_csprng -c -coverage -do "coverage save -onexit trng1_coverage.ucdb; run -all; exit"

clean: 
	rm -rf work transcript
