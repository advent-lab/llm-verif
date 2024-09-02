QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
BASE_DIR ?= /mnt/vault0/asbabbit/ml_for_hdl/GH_Data/riscv-steel_riscv-steel_15
INCLUDES_DIR = $(BASE_DIR)/include

all: worklib compile sim

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs +incdir+$(INCLUDES_DIR) $(BASE_DIR)/design/rvsteel_mcu.v $(BASE_DIR)/design_context/rvsteel_bus.v $(BASE_DIR)/design_context/rvsteel_core.v $(BASE_DIR)/design_context/rvsteel_gpio.v $(BASE_DIR)/design_context/rvsteel_mtimer.v $(BASE_DIR)/design_context/rvsteel_ram.v $(BASE_DIR)/design_context/rvsteel_spi.v $(BASE_DIR)/design_context/rvsteel_uart.v

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.hello_world_cmod_a7 -c -coverage -do "coverage save -onexit fifo_coverage.ucdb; run -all; exit"

clean: 
	rm -rf work transcript
