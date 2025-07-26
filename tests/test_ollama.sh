#!/bin/bash

#SBATCH -N 1            # number of nodes
#SBATCH -c 16            # number of cores 
#SBATCH -t 0-00:30:00
#SBATCH -G a100:2
#SBATCH -C a100_80
#SBATCH -p htc      # partition 
#SBATCH -q public       # QOS
#SBATCH -o slurm.%j.out # file to save job's STDOUT (%j = JobId)
#SBATCH -e slurm.%j.err # file to save job's STDERR (%j = JobId)
#SBATCH --mail-type=ALL # Send an e-mail when a job starts, stops, or fails
#SBATCH --mail-user="%u@asu.edu"
#SBATCH --export=CUDA_VISIBLE_DEVICES=0,1   # Purge the job-submitting shell environment

cd /home/$USER/Research/llm_verif_dataset/llm

export CUDA_VISIBLE_DEVICES=0,1
module load ollama/0.5.5
ollama pull "llama3.1:70b"
ollama list
ollama serve &

#Run the software/python script
./build_llm_venv.sh
source /home/$USER/llm_venv/bin/activate

cd /home/$USER/Research/llm_verif_dataset/llm/tests
python ollama_test.py 2>&1 | tee test_ollama.log
deactivate
rm -rf venv
