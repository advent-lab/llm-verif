#!/bin/bash

#SBATCH -N 1            # number of nodes
#SBATCH -c 32            # number of cores 
#SBATCH -t 0-00:30:00
#SBATCH -G a100:2
#SBATCH -p htc      # partition 
#SBATCH -q public       # QOS
#SBATCH -o slurm.%j.out # file to save job's STDOUT (%j = JobId)
#SBATCH -e slurm.%j.err # file to save job's STDERR (%j = JobId)
#SBATCH --mail-type=ALL # Send an e-mail when a job starts, stops, or fails
#SBATCH --mail-user="%u@asu.edu"
#SBATCH --export=LM_LICENSE_FILE=27006@en4228283l.cidse.dhcp.asu.edu   # Purge the job-submitting shell environment

REPO_DIR=$1
DATA_POINT=$2
NUM_RUNS=$3
RUN=$4

#Load required software
#Change to the directory of our script
rm -rf $REPO_DIR/llm/venv /scratch/$USER/${DATA_POINT}_method6_run_$RUN
mkdir /scratch/$USER/${DATA_POINT}_method6_run_$RUN
cp -rf $REPO_DIR/llm/evaluations $REPO_DIR/llm/src $REPO_DIR/llm/build_llm_venv.sh $REPO_DIR/llm/requirements.txt $REPO_DIR/llm/accelerate_config.yaml /scratch/$USER/${DATA_POINT}_method6_run_$RUN
cd /scratch/$USER/${DATA_POINT}_method6_run_$RUN

#Run the software/python script
./build_llm_venv.sh
source /home/$USER/llm_venv/bin/activate

module load bittware/questa-23.4
export LM_LICENSE_FILE=27006@en4228283l.cidse.dhcp.asu.edu

python evaluations/evaluate_methodology6.py -d $REPO_DIR/data_points/$DATA_POINT -g $NUM_RUNS -c /packages/apps/fpga/Questa/questa_fe/bin 2>&1 | tee ${DATA_POINT}_method6_run_$RUN.log
deactivate
rm -rf venv
