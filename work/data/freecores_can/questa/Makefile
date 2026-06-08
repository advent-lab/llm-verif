QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
DATASET_ROOT ?= /mnt/vault0/ehilaneh/llm_verif_dataset/data_points/
BASE_DIR ?= $(DATASET_ROOT)freecores_can

all: worklib compile sim

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files and test bench files"
	$(QUESTA_ROOT)/vlog -cover bcs \
		+incdir+$(BASE_DIR)/design_context \
		+incdir+$(BASE_DIR)/verif_context \
		$(BASE_DIR)/verif_context/timescale.v \
		$(BASE_DIR)/verif_context/can_testbench_defines.v \
		$(BASE_DIR)/verif/can_testbench.v \
		$(BASE_DIR)/design/can_top.v \
		$(BASE_DIR)/design_context/can_bsp.v \
		$(BASE_DIR)/design_context/can_btl.v \
		$(BASE_DIR)/design_context/can_registers.v \
		$(BASE_DIR)/design_context/can_acf.v \
		$(BASE_DIR)/design_context/can_fifo.v \
		$(BASE_DIR)/design_context/can_crc.v \
		$(BASE_DIR)/design_context/can_ibo.v \
		$(BASE_DIR)/design_context/can_register.v \
		$(BASE_DIR)/design_context/can_register_asyn.v \
		$(BASE_DIR)/design_context/can_register_syn.v \
		$(BASE_DIR)/design_context/can_register_asyn_syn.v

compile_design:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs \
		+incdir+$(BASE_DIR)/design_context \
		$(BASE_DIR)/design/can_top.v \
		$(BASE_DIR)/design_context/can_bsp.v \
		$(BASE_DIR)/design_context/can_btl.v \
		$(BASE_DIR)/design_context/can_registers.v \
		$(BASE_DIR)/design_context/can_acf.v \
		$(BASE_DIR)/design_context/can_fifo.v \
		$(BASE_DIR)/design_context/can_crc.v \
		$(BASE_DIR)/design_context/can_ibo.v \
		$(BASE_DIR)/design_context/can_register.v \
		$(BASE_DIR)/design_context/can_register_asyn.v \
		$(BASE_DIR)/design_context/can_register_syn.v \
		$(BASE_DIR)/design_context/can_register_asyn_syn.v

sim:
	echo "simulating test bench and generating .ucdb coverage report"
	$(QUESTA_ROOT)/vsim work.can_testbench -c -coverage -do "coverage save -onexit freecores_can_coverage.ucdb; run -all; exit"

clean:
	rm -rf work transcript
