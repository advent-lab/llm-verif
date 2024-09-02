QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
BASE_DIR ?= /mnt/vault0/asbabbit/ml_for_hdl/GH_Data/suraj1singh2460_UART_2
INCLUDES_DIR = $(BASE_DIR)/include

all: worklib compile sim

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs +incdir+$(INCLUDES_DIR) $(BASE_DIR)/design/uart_tx.v $(BASE_DIR)/design_context/mux.v $(BASE_DIR)/design_context/parity_calc.v $(BASE_DIR)/design_context/serializer.v $(BASE_DIR)/design_context/tx_fsm.v $(BASE_DIR)/import/param_pkg.sv $(BASE_DIR)/import/uart_pkg.sv $(BASE_DIR)/include/uart_tx_agent.svh $(BASE_DIR)/include/uart_tx_base_sequence.svh $(BASE_DIR)/include/uart_tx_coverage_collector.svh $(BASE_DIR)/include/uart_tx_driver.svh $(BASE_DIR)/include/uart_tx_environment.svh $(BASE_DIR)/include/uart_tx_monitor.svh $(BASE_DIR)/include/uart_tx_scoreboard.svh $(BASE_DIR)/include/uart_tx_sequencer.svh $(BASE_DIR)/include/uart_tx_sequence_item.svh $(BASE_DIR)/include/uart_tx_test.svh

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.uart_tx_top -c -coverage -do "coverage save -onexit fifo_coverage.ucdb; run -all; exit"

clean: 
	rm -rf work transcript
