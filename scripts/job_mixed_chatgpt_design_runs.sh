#!/bin/bash

DESIGNS=("fifo" "vndecorrelator" "sha1_top" "cryptech_uart" "trng_top" "chacha_top")

#"vndecorrelator" "cryptech_uart" "fifo" "trng_top" 

for DESIGN in "${DESIGNS[@]}"; do
	sbatch job_chatgpt_constant_testplan.sh ~/Research/llm_verif_dataset $DESIGN 3 123
	sbatch job_chatgpt_constant_batch.sh ~/Research/llm_verif_dataset $DESIGN 3 123
	sbatch job_chatgpt_constant_temperature.sh ~/Research/llm_verif_dataset $DESIGN 1 123
	sbatch job_chatgpt_logarithmic.sh ~/Research/llm_verif_dataset $DESIGN 3 123
	sbatch job_chatgpt_sigmoid.sh ~/Research/llm_verif_dataset $DESIGN 3 123
done
