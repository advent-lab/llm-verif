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
rm -rf $REPO_DIR/llm/venv /scratch/$USER/temperature_runs/${DATA_POINT}_constant_temperature

mkdir /scratch/$USER/temperature_runs/

mkdir /scratch/$USER/temperature_runs/${DATA_POINT}_constant_temperature_$RUN

cp -rf $REPO_DIR/llm/evaluations $REPO_DIR/llm/src \
    $REPO_DIR/llm/build_llm_venv.sh \
    $REPO_DIR/llm/requirements.txt \
    $REPO_DIR/llm/accelerate_config.yaml \
    /scratch/$USER/temperature_runs

cd /scratch/$USER/temperature_runs

#Run the software/python script
./build_llm_venv.sh
source /home/$USER/llm_venv/bin/activate

module load bittware/questa-23.4
export LM_LICENSE_FILE=27006@en4228283l.scai.dhcp.asu.edu

cd /scratch/$USER/temperature_runs

python /scratch/$USER/temperature_runs/evaluations/evaluate_methodology6.py \
    -d $REPO_DIR/data_points/$DATA_POINT \
    -g $NUM_RUNS \
    -c /packages/apps/fpga/Questa/questa_fe/bin \
    --id "baseline" \
    --model "models--casperhansen--llama-3.3-70b-instruct-awq" \
    --tokenizer "meta-llama/Llama-3.3-70B-Instruct" \
    --quantize \
    -m \
    --temperature_function "constant" \
    --max_iterations 20 \
    --max_valid_iter 10 \
    -o /scratch/$USER/temperature_runs/${DATA_POINT}_constant_temperature_$RUN \
    2>&1 | tee /scratch/$USER/temperature_runs/${DATA_POINT}_constant_temperature_$RUN/${DATA_POINT}_constant_temperature_$RUN.log
    
deactivate
