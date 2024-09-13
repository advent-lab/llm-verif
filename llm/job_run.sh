#!/bin/bash

#SBATCH -N 1            # number of nodes
#SBATCH -c 8            # number of cores 
#SBATCH -G a100:1
#SBATCH -c 
#SBATCH -p general      # partition 
#SBATCH -q public       # QOS
#SBATCH -o slurm.%j.out # file to save job's STDOUT (%j = JobId)
#SBATCH -e slurm.%j.err # file to save job's STDERR (%j = JobId)
#SBATCH --mail-type=ALL # Send an e-mail when a job starts, stops, or fails
#SBATCH --mail-user="%u@asu.edu"
#SBATCH --export=NONE   # Purge the job-submitting shell environment

#Load required software
module load bittware/questa-23.4
export LM_LICENSE_FILE=27006@en4228283.cidse.dhcp.asu.edu

#Change to the directory of our script
cd ~/Research/llm_verif_dataset/llm

#Run the software/python script
python evaluate_hyperparams.py -c /packages/apps/fpga/Questa/questa_fe/bin