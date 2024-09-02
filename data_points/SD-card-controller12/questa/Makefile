QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
BASE_DIR ?= /mnt/vault0/ehilaneh/hw-for-ml-data/Hand_Data/SD-card-controller12

all: worklib compile sim 

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs $(BASE_DIR)/verif/sd_controller_top_tb.sv $(BASE_DIR)/design/sdc_controller.v $(BASE_DIR)/design_context/bistable_domain_cross.v $(BASE_DIR)/design_context/edge_detect.v $(BASE_DIR)/design_context/monostable_domain_cross.v $(BASE_DIR)/design_context/sd_clock_divider.v $(BASE_DIR)/design_context/sd_cmd_master.v $(BASE_DIR)/design_context/sd_cmd_serial_host.v $(BASE_DIR)/design_context/sd_controller_wb.v $(BASE_DIR)/design_context/sd_data_master.v $(BASE_DIR)/design_context/sd_data_serial_host.v $(BASE_DIR)/design_context/sd_data_xfer_trig.v $(BASE_DIR)/design_context/sd_fifo_filler.v $(BASE_DIR)/design_context/sd_wb_sel_ctrl.v $(BASE_DIR)/design_context/sd_crc_7.v $(BASE_DIR)/design_context/generic_fifo_dc_gray.v $(BASE_DIR)/design_context/generic_dpram.v $(BASE_DIR)/design_context/byte_en_reg.v $(BASE_DIR)/design_context/sdModel.v $(BASE_DIR)/design_context/wb_master_behavioral.v $(BASE_DIR)/design_context/wb_slave_behavioral.v $(BASE_DIR)/design_context/wb_bus_mon.v $(BASE_DIR)/design_context/sd_crc_16.v $(BASE_DIR)/design_context/wb_master32.v    

sim: 
	echo "simulating test bench and generating .ucdb coverate report"
	$(QUESTA_ROOT)/vsim work.sd_controller_top_tb -c -coverage -do "coverage save -onexit SD-card-controller12_coverage.ucdb; run -all; exit"

clean: 
	rm -rf work transcript
