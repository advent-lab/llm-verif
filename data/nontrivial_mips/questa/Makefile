QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
DATASET_ROOT ?= /mnt/vault0/ehilaneh/llm_verif_dataset/data_points/
BASE_DIR ?= $(shell cd .. && pwd)
COVERAGE ?= bcs

all: worklib compile sim

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files and test bench files"
	$(QUESTA_ROOT)/vlog -sv -cover $(COVERAGE) \
		+incdir+$(BASE_DIR)/design/cpu \
		+incdir+$(BASE_DIR)/design \
		$(BASE_DIR)/design/nontrivial_mips_impl.sv \
		$(BASE_DIR)/design/cpu/cpu_defs.svh \
		$(BASE_DIR)/design/cpu/cpu_core.sv \
		$(BASE_DIR)/design/cpu/fetch/*.sv \
		$(BASE_DIR)/design/cpu/decode/*.sv \
		$(BASE_DIR)/design/cpu/exec/*.sv \
		$(BASE_DIR)/design/cpu/mem/*.sv \
		$(BASE_DIR)/design/cpu/cp0/*.sv \
		$(BASE_DIR)/design/cpu/regs/*.sv \
		$(BASE_DIR)/design/cpu/mmu/*.sv \
		$(BASE_DIR)/design/cpu/*.sv \
		$(BASE_DIR)/design/asic/*.sv \
		$(BASE_DIR)/design/utils/*.sv \
		$(BASE_DIR)/design/cache/*.sv \
		$(BASE_DIR)/design/mycpu_top.v \
		$(BASE_DIR)/verif/nontrivial_mips_simple_tb.sv

compile_design:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -sv -cover $(COVERAGE) \
		+incdir+$(BASE_DIR)/design/cpu \
		+incdir+$(BASE_DIR)/design \
		$(BASE_DIR)/design/nontrivial_mips_impl.sv \
		$(BASE_DIR)/design/cpu/cpu_defs.svh \
		$(BASE_DIR)/design/cpu/cpu_core.sv \
		$(BASE_DIR)/design/cpu/fetch/*.sv \
		$(BASE_DIR)/design/cpu/decode/*.sv \
		$(BASE_DIR)/design/cpu/exec/*.sv \
		$(BASE_DIR)/design/cpu/mem/*.sv \
		$(BASE_DIR)/design/cpu/cp0/*.sv \
		$(BASE_DIR)/design/cpu/regs/*.sv \
		$(BASE_DIR)/design/cpu/mmu/*.sv \
		$(BASE_DIR)/design/cpu/*.sv \
		$(BASE_DIR)/design/asic/*.sv \
		$(BASE_DIR)/design/utils/*.sv \
		$(BASE_DIR)/design/cache/*.sv \
		$(BASE_DIR)/design/bus/*.sv \
		$(BASE_DIR)/design/interfaces/*.sv \
		$(BASE_DIR)/design/mycpu_top.v

sim:
	echo "simulating test bench and generating .ucdb coverage report"
	$(QUESTA_ROOT)/vsim work.nontrivial_mips_simple_tb -c -coverage -do "coverage save -onexit nontrivial_mips_coverage.ucdb; run -all; exit"

clean:
	rm -rf work transcript *.ucdb
