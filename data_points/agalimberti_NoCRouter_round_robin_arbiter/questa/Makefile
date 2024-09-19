QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
BASE_DIR ?= /mnt/vault0/asbabbit/ml_for_hdl/data_points/agalimberti_NoCRouter_4/src

all: worklib compile sim

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/tb/allocators/tb_round_robin_arbiter.sv $(BASE_DIR)/rtl/allocators/round_robin_arbiter.sv

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.tb_round_robin_arbiter -c -coverage -do "coverage save -onexit tb_round_robin_arbiter.ucdb; run -all; exit"

clean: 
	rm -rf work transcript out.vcd
