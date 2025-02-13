#!/bin/bash

#SBATCH -N 1            # number of nodes
#SBATCH -c 32            # number of cores 
#SBATCH -t 0-10:00:00
#SBATCH -G a100:2
#SBATCH -C a100_80
#SBATCH -p general      # partition 
#SBATCH -q public       # QOS
#SBATCH -o slurm.%j.out # file to save job's STDOUT (%j = JobId)
#SBATCH -e slurm.%j.err # file to save job's STDERR (%j = JobId)
#SBATCH --mail-type=ALL # Send an e-mail when a job starts, stops, or fails
#SBATCH --mail-user="%u@asu.edu"
#SBATCH --export=LM_LICENSE_FILE=27006@en4228283l.scai.dhcp.asu.edu   # Purge the job-submitting shell environment

REPO_DIR=$1
DATA_POINT=$2
NUM_RUNS=$3
RUN=$4

#Load required software
#Change to the directory of our script
rm -rf $REPO_DIR/llm/venv /scratch/$USER/${DATA_POINT}_w_testplan_$RUN /scratch/$USER/${DATA_POINT}_wo_testplan_$RUN
mkdir /scratch/$USER/${DATA_POINT}_w_testplan_$RUN 
mkdir /scratch/$USER/${DATA_POINT}_wo_testplan_$RUN
cp -rf $REPO_DIR/llm/evaluations $REPO_DIR/llm/src $REPO_DIR/llm/build_llm_venv.sh $REPO_DIR/llm/requirements.txt $REPO_DIR/llm/accelerate_config.yaml /scratch/$USER/${DATA_POINT}_w_tesplan_$RUN
cp -rf $REPO_DIR/llm/evaluations $REPO_DIR/llm/src $REPO_DIR/llm/build_llm_venv.sh $REPO_DIR/llm/requirements.txt $REPO_DIR/llm/accelerate_config.yaml /scratch/$USER/${DATA_POINT}_wo_testplan_$RUN

#Run the software/python script
source /home/$USER/llm_venv/bin/activate

module load bittware/questa-23.4
export LM_LICENSE_FILE=27006@en4228283l.scai.dhcp.asu.edu

cd /scratch/$USER/${DATA_POINT}_w_testplan_$RUN
python evaluations/evaluate_methodology6.py -d $REPO_DIR/data_points/$DATA_POINT -g $NUM_RUNS -c /packages/apps/fpga/Questa/questa_fe/bin --no_sampling -S -m --testplan --remove_polluted_context --max_iterations 20 --max_valid_iter 10 -b 5 2>&1 | tee ${DATA_POINT}_w_testplan_$RUN.log
cd /scratch/$USER/${DATA_POINT}_wo_testplan_$RUN
python evaluations/evaluate_methodology6.py -d $REPO_DIR/data_points/$DATA_POINT -g $NUM_RUNS -c /packages/apps/fpga/Questa/questa_fe/bin --no_sampling -S -m --remove_polluted_context --max_iterations 20 --max_valid_iter 10 -b 5 2>&1 | tee ${DATA_POINT}_wo_testplan_$RUN.log


deactivate
rm -rf venv
