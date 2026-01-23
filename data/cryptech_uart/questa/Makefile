QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
DATASET_ROOT ?= /mnt/vault0/ehilaneh/llm_verif_dataset/data_points/
BASE_DIR ?= $(DATASET_ROOT)cryptech_uart

all: worklib compile sim

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files and test files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/verif/tb_uart.v $(BASE_DIR)/design_context/uart_regs.v $(BASE_DIR)/design/uart_core.v

compile_design:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/design_context/uart_regs.v $(BASE_DIR)/design/uart_core.v

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.tb_uart -c -coverage -do "coverage save -onexit cryptech_uart_coverage.ucdb; run -all; exit"

clean: 
	rm -rf work transcript
