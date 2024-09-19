QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
BASE_DIR ?= /mnt/vault0/ehilaneh/llm_verif_dataset/data_points/gsoc-museum-edsac_1

all: worklib compile sim

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/test/edsac/misc/flipflop_tb.v $(BASE_DIR)/src/edsac/misc/flipflop.v

sim: 
	echo "simulating test bench and generating .ucdb coverage report"
	$(QUESTA_ROOT)/vsim work.flipflop_tb -c -coverage -do "coverage save -onexit flipflop_tb.ucdb; run -all; exit"

clean: 
	rm -rf work transcript flipflop.vcd
