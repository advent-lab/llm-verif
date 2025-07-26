#!/bin/bash

sbatch job_constant_temperature.sh ~/Research/llm_verif_dataset sha1_top 3 0
sbatch job_logarithmic_temperature.sh ~/Research/llm_verif_dataset sha1_top 3 0
sbatch job_sigmoid_temperature.sh ~/Research/llm_verif_dataset sha1_top 3 0
sbatch job_constant_temperature.sh ~/Research/llm_verif_dataset chacha_top 3 0
sbatch job_logarithmic_temperature.sh ~/Research/llm_verif_dataset chacha_top 3 0
sbatch job_sigmoid_temperature.sh ~/Research/llm_verif_dataset chacha_top 3 0
