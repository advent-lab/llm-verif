QUESTA_ROOT ?= /mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin
DATASET_ROOT ?= /mnt/vault0/ehilaneh/llm_verif_dataset/data_points/
BASE_DIR ?= $(DATASET_ROOT)jpegencode

all: worklib compile sim

worklib:
	echo "creating worklib"
	$(QUESTA_ROOT)/vlib work

compile:
	echo "compiling design files and test bench files"
	$(QUESTA_ROOT)/vlog -cover bcs \
		$(TB_FILE) \
		$(BASE_DIR)/design_context/sync_fifo_32.v \
		$(BASE_DIR)/design_context/sync_fifo_ff.v \
		$(BASE_DIR)/design_context/rgb2ycbcr.v \
		$(BASE_DIR)/design_context/y_dct.v \
		$(BASE_DIR)/design_context/y_quantizer.v \
		$(BASE_DIR)/design_context/y_huff.v \
		$(BASE_DIR)/design_context/cb_dct.v \
		$(BASE_DIR)/design_context/cb_quantizer.v \
		$(BASE_DIR)/design_context/cb_huff.v \
		$(BASE_DIR)/design_context/cr_dct.v \
		$(BASE_DIR)/design_context/cr_quantizer.v \
		$(BASE_DIR)/design_context/cr_huff.v \
		$(BASE_DIR)/design_context/yd_q_h.v \
		$(BASE_DIR)/design_context/cbd_q_h.v \
		$(BASE_DIR)/design_context/crd_q_h.v \
		$(BASE_DIR)/design_context/pre_fifo.v \
		$(BASE_DIR)/design_context/fifo_out.v \
		$(BASE_DIR)/design_context/ff_checker.v \
		$(BASE_DIR)/design/jpeg_top.v

compile_design:
	echo "compiling design files"
	$(QUESTA_ROOT)/vlog -cover bcs \
		$(BASE_DIR)/design_context/sync_fifo_32.v \
		$(BASE_DIR)/design_context/sync_fifo_ff.v \
		$(BASE_DIR)/design_context/rgb2ycbcr.v \
		$(BASE_DIR)/design_context/y_dct.v \
		$(BASE_DIR)/design_context/y_quantizer.v \
		$(BASE_DIR)/design_context/y_huff.v \
		$(BASE_DIR)/design_context/cb_dct.v \
		$(BASE_DIR)/design_context/cb_quantizer.v \
		$(BASE_DIR)/design_context/cb_huff.v \
		$(BASE_DIR)/design_context/cr_dct.v \
		$(BASE_DIR)/design_context/cr_quantizer.v \
		$(BASE_DIR)/design_context/cr_huff.v \
		$(BASE_DIR)/design_context/yd_q_h.v \
		$(BASE_DIR)/design_context/cbd_q_h.v \
		$(BASE_DIR)/design_context/crd_q_h.v \
		$(BASE_DIR)/design_context/pre_fifo.v \
		$(BASE_DIR)/design_context/fifo_out.v \
		$(BASE_DIR)/design_context/ff_checker.v \
		$(BASE_DIR)/design/jpeg_top.v

sim:
	echo "simulating test bench and generating .ucdb coverage report"
	$(QUESTA_ROOT)/vsim work.tb_jpegencode -c -coverage -do "coverage save -onexit jpegencode_coverage.ucdb; run -all; exit"

clean:
	rm -rf work transcript
