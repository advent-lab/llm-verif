QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
BASE_DIR ?= /mnt/vault0/ehilaneh/hw-for-ml-data/Hand_Data/SD-card-controller5

all: worklib compile sim 

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/verif/sd_cmd_serial_host_tb.sv $(BASE_DIR)/design/sd_cmd_serial_host.v $(BASE_DIR)/design_context/sd_crc_7.v   

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.sd_cmd_serial_host_tb -c -coverage -do "coverage save -onexit SD-card-controller5_coverage.ucdb; run -all; exit"

clean: 
	rm -rf work transcript
