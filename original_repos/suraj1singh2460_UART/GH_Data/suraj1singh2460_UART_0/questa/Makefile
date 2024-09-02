QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
BASE_DIR ?= /mnt/vault0/asbabbit/ml_for_hdl/GH_Data/suraj1singh2460_UART_0
INCLUDES_DIR = $(BASE_DIR)/include

all: worklib compile sim

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs +incdir+$(INCLUDES_DIR) $(BASE_DIR)/design/uart_rx.v $(BASE_DIR)/design/uart_tx.v $(BASE_DIR)/design_context/data_sampling.v $(BASE_DIR)/design_context/deserializer.v $(BASE_DIR)/design_context/edge_bit_counter.v $(BASE_DIR)/design_context/mux.v $(BASE_DIR)/design_context/parity_calc.v $(BASE_DIR)/design_context/parity_check.v $(BASE_DIR)/design_context/rx_fsm.v $(BASE_DIR)/design_context/serializer.v $(BASE_DIR)/design_context/start_check.v $(BASE_DIR)/design_context/stop_check.v $(BASE_DIR)/design_context/tx_fsm.v

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.uart -c -coverage -do "coverage save -onexit fifo_coverage.ucdb; run -all; exit"

clean: 
	rm -rf work transcript
