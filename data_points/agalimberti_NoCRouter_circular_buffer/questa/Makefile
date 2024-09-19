QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
BASE_DIR ?= /mnt/vault0/asbabbit/ml_for_hdl/data_points/agalimberti_NoCRouter_1

all: worklib compile sim

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/src/rtl/noc/noc.sv $(BASE_DIR)/src/rtl/input_port/circular_buffer.sv $(BASE_DIR)/src/tb/input_port/tb_circular_buffer.sv

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.tb_circular_buffer -c -coverage -do "coverage save -onexit tb_circular_buffer.ucdb; run -all; exit"

clean: 
	rm -rf work transcript out.vcd
