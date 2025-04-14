#!/bin/bash

DESIGNS=("sha1_top" "cryptech_uart" "chacha_top")
ITER=(0 1 2)

#"vndecorrelator" "cryptech_uart" "fifo" "trng_top" 

for DESIGN in "${DESIGNS[@]}"; do
	for RUN in ${ITER[@]}; do
		sbatch job_constant_testplan.sh ~/Research/llm_verif_dataset $DESIGN 1 $RUN
		sbatch job_constant_batch.sh ~/Research/llm_verif_dataset $DESIGN 1 $RUN
		sbatch job_constant_temperature.sh ~/Research/llm_verif_dataset $DESIGN 1 $RUN
		sbatch job_logarithmic_temperature.sh ~/Research/llm_verif_dataset $DESIGN 1 $RUN
		sbatch job_sigmoid_temperature.sh ~/Research/llm_verif_dataset $DESIGN 1 $RUN
	done
done
