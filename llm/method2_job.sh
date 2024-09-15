#!/bin/bash

#SBATCH -N 1            # number of nodes
#SBATCH -c 32            # number of cores 
#SBATCH --mem=128G
#SBATCH -t 1-00:00:00
#SBATCH -G a100:2
#SBATCH -C a100_80
#SBATCH -p general      # partition 
#SBATCH -q public       # QOS
#SBATCH -o slurm.%j.out # file to save job's STDOUT (%j = JobId)
#SBATCH -e slurm.%j.err # file to save job's STDERR (%j = JobId)
#SBATCH --mail-type=ALL # Send an e-mail when a job starts, stops, or fails
#SBATCH --mail-user="%u@asu.edu"
#SBATCH --export=NONE   # Purge the job-submitting shell environment

#Load required software
#Change to the directory of our script
rm -rf ~/Research/llm_verif_dataset/llm/venv
cp -r ~/Research/llm_verif_dataset/llm /scratch/slowe8/method2_runs
cd /scratch/slowe8/method2_runs

#Run the software/python script
module load mamba/latest
source activate scicomp
python -m venv venv
deactivate
source venv/bin/activate
pip install -r requirements.txt

module load bittware/questa-23.4
export LM_LICENSE_FILE=27006@en4228283l.cidse.dhcp.asu.edu

python evaluate_methodology2.py -g 10 -c /packages/apps/fpga/Questa/questa_fe/bin #> method2_job.log
deactivate
rm -rf venv