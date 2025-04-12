#!/bin/bash

DESIGNS=("sha1_top" "cryptech_uart" "trng_top" "chacha_top")

#"vndecorrelator" "cryptech_uart" "fifo" "trng_top" 

for DESIGN in "${DESIGNS[@]}"; do
	sbatch job_constant_testplan.sh ~/Research/llm_verif_dataset $DESIGN 3 123
	sbatch job_constant_batch.sh ~/Research/llm_verif_dataset $DESIGN 3 123
	sbatch job_constant_temperature.sh ~/Research/llm_verif_dataset $DESIGN 3 123
	sbatch job_logarithmic_temperature.sh ~/Research/llm_verif_dataset $DESIGN 3 123
	sbatch job_sigmoid_temperature.sh ~/Research/llm_verif_dataset $DESIGN 3 123
done
