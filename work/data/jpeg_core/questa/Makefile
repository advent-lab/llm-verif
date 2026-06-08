QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
DATASET_ROOT ?= /mnt/vault0/ehilaneh/llm_verif_dataset/data_points/
BASE_DIR ?= $(DATASET_ROOT)jpeg_core

all: worklib compile sim

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files and test bench files"
	$(QUESTA_ROOT)/vlog -cover bcs \
		$(BASE_DIR)/verif/tb_jpeg_core.v \
		$(BASE_DIR)/design_context/jpeg_dht_std_y_dc.v \
		$(BASE_DIR)/design_context/jpeg_dht_std_y_ac.v \
		$(BASE_DIR)/design_context/jpeg_dht_std_cx_dc.v \
		$(BASE_DIR)/design_context/jpeg_dht_std_cx_ac.v \
		$(BASE_DIR)/design_context/jpeg_idct_ram_dp.v \
		$(BASE_DIR)/design_context/jpeg_idct_transpose_ram.v \
		$(BASE_DIR)/design_context/jpeg_idct_x.v \
		$(BASE_DIR)/design_context/jpeg_idct_y.v \
		$(BASE_DIR)/design_context/jpeg_idct_fifo.v \
		$(BASE_DIR)/design_context/jpeg_mcu_id.v \
		$(BASE_DIR)/design_context/jpeg_output_y_ram.v \
		$(BASE_DIR)/design_context/jpeg_output_cx_ram.v \
		$(BASE_DIR)/design_context/jpeg_output_fifo.v \
		$(BASE_DIR)/design_context/jpeg_input.v \
		$(BASE_DIR)/design_context/jpeg_bitbuffer.v \
		$(BASE_DIR)/design_context/jpeg_dqt.v \
		$(BASE_DIR)/design_context/jpeg_dht.v \
		$(BASE_DIR)/design_context/jpeg_idct_ram.v \
		$(BASE_DIR)/design_context/jpeg_idct_transpose.v \
		$(BASE_DIR)/design_context/jpeg_idct.v \
		$(BASE_DIR)/design_context/jpeg_mcu_proc.v \
		$(BASE_DIR)/design_context/jpeg_output.v \
		$(BASE_DIR)/design/jpeg_core.v

compile_design:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs \
		$(BASE_DIR)/design_context/jpeg_dht_std_y_dc.v \
		$(BASE_DIR)/design_context/jpeg_dht_std_y_ac.v \
		$(BASE_DIR)/design_context/jpeg_dht_std_cx_dc.v \
		$(BASE_DIR)/design_context/jpeg_dht_std_cx_ac.v \
		$(BASE_DIR)/design_context/jpeg_idct_ram_dp.v \
		$(BASE_DIR)/design_context/jpeg_idct_transpose_ram.v \
		$(BASE_DIR)/design_context/jpeg_idct_x.v \
		$(BASE_DIR)/design_context/jpeg_idct_y.v \
		$(BASE_DIR)/design_context/jpeg_idct_fifo.v \
		$(BASE_DIR)/design_context/jpeg_mcu_id.v \
		$(BASE_DIR)/design_context/jpeg_output_y_ram.v \
		$(BASE_DIR)/design_context/jpeg_output_cx_ram.v \
		$(BASE_DIR)/design_context/jpeg_output_fifo.v \
		$(BASE_DIR)/design_context/jpeg_input.v \
		$(BASE_DIR)/design_context/jpeg_bitbuffer.v \
		$(BASE_DIR)/design_context/jpeg_dqt.v \
		$(BASE_DIR)/design_context/jpeg_dht.v \
		$(BASE_DIR)/design_context/jpeg_idct_ram.v \
		$(BASE_DIR)/design_context/jpeg_idct_transpose.v \
		$(BASE_DIR)/design_context/jpeg_idct.v \
		$(BASE_DIR)/design_context/jpeg_mcu_proc.v \
		$(BASE_DIR)/design_context/jpeg_output.v \
		$(BASE_DIR)/design/jpeg_core.v

sim:
	echo "simulating test bench and generating .ucdb coverage report"
	$(QUESTA_ROOT)/vsim work.tb_jpeg_core -c -coverage -do "coverage save -onexit jpeg_core_coverage.ucdb; run -all; exit"

clean:
	rm -rf work transcript
