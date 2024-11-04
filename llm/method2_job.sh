#!/bin/bash

#SBATCH -N 1            # number of nodes
#SBATCH -c 32            # number of cores 
#SBATCH --mem=128G
#SBATCH -t 02:00:00
#SBATCH -G a100:2
#SBATCH -C a100_80
#SBATCH -p general      # partition 
#SBATCH -q public       # QOS
#SBATCH -o slurm.%j.out # file to save job's STDOUT (%j = JobId)
#SBATCH -e slurm.%j.err # file to save job's STDERR (%j = JobId)
#SBATCH --mail-type=ALL # Send an e-mail when a job starts, stops, or fails
#SBATCH --mail-user="%u@asu.edu"
#SBATCH --export=LM_LICENSE_FILE=27006@en4228283l.cidse.dhcp.asu.edu   # Purge the job-submitting shell environment

REPO_DIR=$1
DATA_POINT=$2

#Load required software
#Change to the directory of our script
rm -rf $REPO_DIR/llm/venv /scratch/$USER/${DATA_POINT}_method2_runs
cp -rf $REPO_DIR/llm /scratch/$USER/${DATA_POINT}_method2_runs
cd /scratch/$USER/${DATA_POINT}_method2_runs

#Run the software/python script
./build_llm_venv.sh
source /home/$USER/llm_venv/bin/activate

module load bittware/questa-23.4
export LM_LICENSE_FILE=27006@en4228283l.cidse.dhcp.asu.edu

python evaluate_methodology2.py -d $REPO_DIR/data_points/$DATA_POINT -g 10 -c /packages/apps/fpga/Questa/questa_fe/bin #> method2_job.log
deactivate
rm -rf venv
