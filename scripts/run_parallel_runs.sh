#!/bin/bash

for i in {0..4}
do
	sbatch method6_job.sh ~/Research/llm_verif_dataset fifo 1 $i
	sbatch method6_job.sh ~/Research/llm_verif_dataset mkmif_core 1 $i
	sbatch method6_job.sh ~/Research/llm_verif_dataset sha1_core 1 $i
	sbatch method6_job.sh ~/Research/llm_verif_dataset chacha_core 1 $i
	sbatch method6_job.sh ~/Research/llm_verif_dataset sha1_top 1 $i
	sbatch method6_job.sh ~/Research/llm_verif_dataset chacha_top 1 $i
done
