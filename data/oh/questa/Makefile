QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
BASE_DIR ?= $(shell cd ../.. && pwd)
COVERAGE ?= bcs
PROJECT_DIR ?= $(BASE_DIR)/oh
PROJECT_FILES ?=  $(PROJECT_DIR)/edma/dv/dut_edma.v $(PROJECT_DIR)/edma/hdl/edma.v $(PROJECT_DIR)/edma/hdl/edma_dp.v $(PROJECT_DIR)/edma/hdl/edma_regmap.vh $(PROJECT_DIR)/edma/hdl/packet2emesh.v $(PROJECT_DIR)/edma/hdl/edma_regs.v $(PROJECT_DIR)/edma/hdl/oh_mux3.v $(PROJECT_DIR)/edma/hdl/emesh2packet.v $(PROJECT_DIR)/edma/hdl/edma_ctrl.v

all: worklib compile sim

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -sv -cover $(COVERAGE) $(PROJECT_FILES)

sim: 
	echo "simulating test bench and generating .ucdb coverage report"
	$(QUESTA_ROOT)/vsim work.dut -c -coverage -do "coverage save -onexit dut.ucdb; run -all; exit"

clean: 
	rm -rf work transcript
