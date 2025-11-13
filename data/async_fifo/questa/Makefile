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
		$(BASE_DIR)/design/fifomem.v \
		$(BASE_DIR)/design/sync_r2w.v \
		$(BASE_DIR)/design/sync_w2r.v \
		$(BASE_DIR)/design/rptr_empty.v \
		$(BASE_DIR)/design/wptr_full.v \
		$(BASE_DIR)/design/async_fifo.v \
		$(BASE_DIR)/verif/svut_h.sv \
		$(BASE_DIR)/verif/async_fifo_unit_test.sv

sim:
	echo "simulating test bench and generating .ucdb coverage report"
	$(QUESTA_ROOT)/vsim work.async_fifo_unit_test -c -coverage \
		-do "coverage save -onexit async_fifo_coverage.ucdb; run -all; exit"

clean:
	rm -rf work transcript *.ucdb
