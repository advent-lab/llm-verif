QUESTA_ROOT ?= /packages/apps/fpga/Questa/questa_fe/bin
BASE_DIR ?= ./sha12/design
TB_LLM ?= tb_llm

all: worklib compile sim report

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover s $(shell echo $(BASE_DIR)/*.v)

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.$(TB_LLM) -coverage -c -do questa_coverage.do

report:
	echo "generating coverage report"
	$(QUESTA_ROOT)/vcover report coverage.ucdb > coverage_report.txt

clean: 
	rm -rf work $(BASE_DIR)/work transcript
