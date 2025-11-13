QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
DATASET_ROOT ?= /mnt/vault0/ehilaneh/llm_verif_dataset/data_points/
BASE_DIR ?= $(shell cd .. && pwd)
COVERAGE ?= bcs

all: worklib compile sim 

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files and test files"
	$(QUESTA_ROOT)/vlog -sv -cover $(COVERAGE) $(BASE_DIR)/verif/tb_ethernet.v $(BASE_DIR)/verif/eth_host.v $(BASE_DIR)/verif/eth_memory.v $(BASE_DIR)/verif/eth_phy.v $(BASE_DIR)/design_context/wb_bus_mon.v $(BASE_DIR)/design_context/wb_master_behavioral.v $(BASE_DIR)/design_context/wb_master32.v $(BASE_DIR)/design_context/wb_slave_behavioral.v $(BASE_DIR)/design/eth_clockgen.v $(BASE_DIR)/design/eth_cop.v $(BASE_DIR)/design/eth_crc.v $(BASE_DIR)/design/eth_fifo.v $(BASE_DIR)/design/eth_maccontrol.v $(BASE_DIR)/design/eth_macstatus.v $(BASE_DIR)/design/eth_miim.v $(BASE_DIR)/design/eth_outputcontrol.v $(BASE_DIR)/design/eth_random.v $(BASE_DIR)/design/eth_receivecontrol.v $(BASE_DIR)/design/eth_register.v $(BASE_DIR)/design/eth_registers.v $(BASE_DIR)/design/eth_rxaddrcheck.v $(BASE_DIR)/design/eth_rxcounters.v $(BASE_DIR)/design/eth_rxethmac.v $(BASE_DIR)/design/eth_rxstatem.v $(BASE_DIR)/design/eth_shiftreg.v $(BASE_DIR)/design/eth_spram_256x32.v $(BASE_DIR)/design/eth_transmitcontrol.v $(BASE_DIR)/design/eth_txcounters.v $(BASE_DIR)/design/eth_txethmac.v $(BASE_DIR)/design/eth_txstatem.v $(BASE_DIR)/design/eth_wishbone.v $(BASE_DIR)/design/ethmac.v $(BASE_DIR)/design/xilinx_dist_ram_16x32.v

compile_design:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -sv -cover $(COVERAGE) $(BASE_DIR)/verif/eth_host.v $(BASE_DIR)/verif/eth_memory.v $(BASE_DIR)/verif/eth_phy.v $(BASE_DIR)/design_context/wb_bus_mon.v $(BASE_DIR)/design_context/wb_master_behavioral.v $(BASE_DIR)/design_context/wb_master32.v $(BASE_DIR)/design_context/wb_slave_behavioral.v $(BASE_DIR)/design/eth_clockgen.v $(BASE_DIR)/design/eth_cop.v $(BASE_DIR)/design/eth_crc.v $(BASE_DIR)/design/eth_fifo.v $(BASE_DIR)/design/eth_maccontrol.v $(BASE_DIR)/design/eth_macstatus.v $(BASE_DIR)/design/eth_miim.v $(BASE_DIR)/design/eth_outputcontrol.v $(BASE_DIR)/design/eth_random.v $(BASE_DIR)/design/eth_receivecontrol.v $(BASE_DIR)/design/eth_register.v $(BASE_DIR)/design/eth_registers.v $(BASE_DIR)/design/eth_rxaddrcheck.v $(BASE_DIR)/design/eth_rxcounters.v $(BASE_DIR)/design/eth_rxethmac.v $(BASE_DIR)/design/eth_rxstatem.v $(BASE_DIR)/design/eth_shiftreg.v $(BASE_DIR)/design/eth_spram_256x32.v $(BASE_DIR)/design/eth_transmitcontrol.v $(BASE_DIR)/design/eth_txcounters.v $(BASE_DIR)/design/eth_txethmac.v $(BASE_DIR)/design/eth_txstatem.v $(BASE_DIR)/design/eth_wishbone.v $(BASE_DIR)/design/ethmac.v $(BASE_DIR)/design/xilinx_dist_ram_16x32.v

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.tb_ethernet -c -coverage -do "coverage save -onexit ethmac0_coverage.ucdb; run -all; exit"

clean: 
	rm -rf work transcript
