#!/bin/bash

DESIGNS=("activation" "mkmif_top" "pooling" "simple_mat_mul" "stop_watch" "TrafficLightController_Main" "verilog-divider")
ITER=(0 1 2)

# "sha1_top" "cryptech_uart" "chacha_top" "vndecorrelator" "fifo" "trng_top" 

for DESIGN in "${DESIGNS[@]}"; do
	for RUN in ${ITER[@]}; do
		sbatch job_constant_testplan.sh ~/Research/llm_verif_dataset $DESIGN 1 $RUN
		sbatch job_constant_batch.sh ~/Research/llm_verif_dataset $DESIGN 1 $RUN
		sbatch job_constant_temperature.sh ~/Research/llm_verif_dataset $DESIGN 1 $RUN
		sbatch job_logarithmic_temperature.sh ~/Research/llm_verif_dataset $DESIGN 1 $RUN
		sbatch job_sigmoid_temperature.sh ~/Research/llm_verif_dataset $DESIGN 1 $RUN
	done
done
