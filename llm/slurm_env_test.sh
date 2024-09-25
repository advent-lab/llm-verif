#!/bin/bash

#SBATCH -N 1            # number of nodes
#SBATCH -c 1            # number of cores
#SBATCH -t 0-00:05:00
#SBATCH -p general      # partition 
#SBATCH -q public       # QOS
#SBATCH -o slurm.%j.out # file to save job's STDOUT (%j = JobId)
#SBATCH -e slurm.%j.err # file to save job's STDERR (%j = JobId)
#SBATCH --mail-type=ALL # Send an e-mail when a job starts, stops, or fails
#SBATCH --mail-user="%u@asu.edu"
#SBATCH --export=NONE   # Purge the job-submitting shell environment

export LM_LICENSE_FILE=27006@en4228283l.cidse.dhcp.asu.edu
echo $LM_LICENSE_FILE

module load bittware/questa-23.4
cd ~/Research/llm_verif_dataset/llm/sha12/design
vlog -cover s *.v
vsim -coverage -c "coverage save -onexit ../../coverage_slurm.ucdb; run -all; exit;"
vcover report ../../coverage_slurm.ucdb