#!/bin/bash

for i in {0..4}
do
	sbatch method6_job.sh ~/Research/llm_verif_dataset fifo $i
	sbatch method6_job.sh ~/Research/llm_verif_dataset mkmif_core $i
	sbatch method6_job.sh ~/Research/llm_verif_dataset sha1_core $i
	sbatch method6_job.sh ~/Research/llm_verif_dataset chacha_core $i
	sbatch method6_job.sh ~/Research/llm_verif_dataset sha1_top $i
	sbatch method6_job.sh ~/Research/llm_verif_dataset chacha_top $i
done
