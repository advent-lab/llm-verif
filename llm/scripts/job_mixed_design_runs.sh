#!/bin/bash

DESIGNS=("chacha_top" "sha1_top" "cryptech_uart" "trng_top")

#"vndecorrelator" "cryptech_uart" "fifo" "trng_top" 

for DESIGN in "${DESIGNS[@]}"; do
	sbatch job_constant_testplan.sh ~/Research/llm_verif_dataset $DESIGN 1 0
	sbatch job_constant_batch.sh ~/Research/llm_verif_dataset $DESIGN 1 0
	sbatch job_constant_temperature.sh ~/Research/llm_verif_dataset $DESIGN 1 0
	sbatch job_logarithmic_temperature.sh ~/Research/llm_verif_dataset $DESIGN 1 0
	sbatch job_sigmoid_temperature.sh ~/Research/llm_verif_dataset $DESIGN 1 0
done

sleep 5m

for DESIGN in "${DESIGN[@]}"; do
	sbatch job_constant_testplan.sh ~/Research/llm_verif_dataset $DESIGN 1 1
	sbatch job_constant_batch.sh ~/Research/llm_verif_dataset $DESIGN 1 1
	sbatch job_constant_temperature.sh ~/Research/llm_verif_dataset $DESIGN 1 1
	sbatch job_logarithmic_temperature.sh ~/Research/llm_verif_dataset $DESIGN 1 1
	sbatch job_sigmoid_temperature.sh ~/Research/llm_verif_dataset $DESIGN 1 1
done
