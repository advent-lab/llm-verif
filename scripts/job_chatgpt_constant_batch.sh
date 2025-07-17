#!/bin/bash

#SBATCH -N 1            # number of nodes
#SBATCH -c 16            # number of cores 
#SBATCH --mem 64GB
#SBATCH -t 0-05:00:00
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
rm -rf $REPO_DIR/llm/venv /scratch/$USER/chatgpt_runs/${DATA_POINT}_constant_batch_chatgpt 

mkdir /scratch/$USER/chatgpt_runs

mkdir /scratch/$USER/chatgpt_runs/${DATA_POINT}_constant_batch_chatgpt_$RUN

cp -rf $REPO_DIR/llm/evaluations $REPO_DIR/llm/src \
    $REPO_DIR/llm/build_llm_venv.sh \
    $REPO_DIR/llm/requirements.txt \
    $REPO_DIR/llm/accelerate_config.yaml \
    /scratch/$USER/chatgpt_runs

cd /scratch/$USER/chatgpt_runs

#Run the software/python script
./build_llm_venv.sh
source /home/$USER/llm_venv/bin/activate

module load bittware/questa-23.4
export LM_LICENSE_FILE=27006@en4228283l.scai.dhcp.asu.edu

cd /scratch/$USER/chatgpt_runs

python /scratch/$USER/chatgpt_runs/evaluations/evaluate_chatgpt-4o.py \
    -d $REPO_DIR/data_points/$DATA_POINT \
    -g $NUM_RUNS \
    -c /packages/apps/fpga/Questa/questa_fe/bin \
    --dotenv_path /home/slowe8/Research/llm_verif_dataset/llm/.env \
    --id "chatgpt project run" \
    --model "gpt-4o" \
    --tokenizer "meta-llama/Llama-3.3-70B-Instruct" \
    -m \
    --temperature_function "capped_sigmoid" \
    --testplan \
    --max_iterations 20 \
    --max_valid_iter 10 \
    -b 5 \
    -o /scratch/$USER/chatgpt_runs/${DATA_POINT}_constant_batch_chatgpt_$RUN \
    2>&1 | tee /scratch/$USER/chatgpt_runs/${DATA_POINT}_constant_batch_chatgpt_$RUN/${DATA_POINT}_constant_batch_chatgpt_$RUN.log
    
deactivate
