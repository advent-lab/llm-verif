#!/bin/bash

DATASET_PATH=$1

DESIGNS=("sha1_top" "cryptech_uart" "chacha_top" "simple_mat_mul" "pooling" "activation" "float_add" "float_multiplier")
ITER=(0 1 2)

# Base Set: "sha1_top" "cryptech_uart" "chacha_top"
# Extended Set: "activation" "mkmif_top" "pooling" "simple_mat_mul" "stop_watch" "TrafficLightController_Main" "verilog-divider"
# Don't run: "vndecorrelator" "fifo" "trng_top" 

for DESIGN in "${DESIGNS[@]}"; do
	for RUN in ${ITER[@]}; do
		sbatch group_job.sh ${DATASET_PATH} constant $DESIGN 1 $RUN
		sbatch group_job.sh ${DATASET_PATH} logarithmic $DESIGN 1 $RUN
		sbatch group_job.sh ${DATASET_PATH} sigmoid $DESIGN 1 $RUN
		sbatch group_job.sh ${DATASET_PATH} batch $DESIGN 1 $RUN
		sbatch group_job.sh ${DATASET_PATH} testplan $DESIGN 1 $RUN
	done
done
