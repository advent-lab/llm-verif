QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
BASE_DIR ?= $(shell cd .. && pwd)
COVERAGE ?= bcs

all: worklib compile sim

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files and test bench files"
	$(QUESTA_ROOT)/vlog -sv -cover $(COVERAGE) \
		$(BASE_DIR)/design/sdram_controller.v \
		$(BASE_DIR)/design/fifo.v \
		$(BASE_DIR)/design/double_click.v \
		$(BASE_DIR)/design/dnano_interface.v \
		$(BASE_DIR)/verif/vlog_tb_utils.v \
		$(BASE_DIR)/verif/sdram_controller_tb.v

sim:
	echo "simulating test bench and generating .ucdb coverage report"
	$(QUESTA_ROOT)/vsim work.sdram_controller_tb -c -coverage \
		-do "coverage save -onexit sdram_controller_coverage.ucdb; run -all; exit"

clean:
	rm -rf work transcript *.ucdb
