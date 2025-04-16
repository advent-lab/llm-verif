#!/bin/bash

#SBATCH -N 1            # number of nodes
#SBATCH -c 32            # number of cores 
#SBATCH --mem 64GB
#SBATCH -t 0-06:00:00
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
RUN_TYPE=$2
DATA_POINT=$3
NUM_RUNS=$4
RUN=$5

#Load required software
#Change to the directory of our script
mkdir /scratch/$USER/runs/
rm -r /scratch/$USER/runs/${DATA_POINT}_${RUN_TYPE}_$RUN
mkdir /scratch/$USER/runs/${DATA_POINT}_${RUN_TYPE}_$RUN
cp -rf $REPO_DIR/llm/evaluations \
    $REPO_DIR/llm/src \
    $REPO_DIR/llm/build_llm_venv.sh \
    $REPO_DIR/llm/requirements.txt \
    $REPO_DIR/llm/accelerate_config.yaml \
    /scratch/$USER/runs

cd /scratch/$USER/runs

#Run the software/python script
./build_llm_venv.sh
source /home/$USER/llm_venv/bin/activate

module load bittware/questa-23.4
export LM_LICENSE_FILE=27006@en4228283l.scai.dhcp.asu.edu

cd /scratch/$USER/runs

if [ "$RUN_TYPE" == "logarithmic" ]; then

    python /scratch/$USER/runs/evaluations/evaluate_methodology6.py \
        -d $REPO_DIR/data_points/$DATA_POINT \
        -g $NUM_RUNS \
        -c /packages/apps/fpga/Questa/questa_fe/bin \
        --id "logarithmic" \
        --model "models--casperhansen--llama-3.3-70b-instruct-awq" \
        --tokenizer "meta-llama/Llama-3.3-70B-Instruct" \
        --quantize \
        -m \
        --temperature_function "logarithmic" \
        --max_iterations 20 \
        --max_valid_iter 10 \
        -o /scratch/$USER/runs/${DATA_POINT}_logarithmic_$RUN \
        2>&1 | tee /scratch/$USER/runs/${DATA_POINT}_logarithmic_$RUN/${DATA_POINT}_logarithmic_$RUN.log

elif [ "$RUN_TYPE" == "constant" ]; then

    python /scratch/$USER/runs/evaluations/evaluate_methodology6.py \
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
        -o /scratch/$USER/runs/${DATA_POINT}_constant_$RUN \
        2>&1 | tee /scratch/$USER/runs/${DATA_POINT}_constant_$RUN/${DATA_POINT}_constant_$RUN.log

elif [ "$RUN_TYPE" == "sigmoid" ]; then

    python /scratch/$USER/runs/evaluations/evaluate_methodology6.py \
        -d $REPO_DIR/data_points/$DATA_POINT \
        -g $NUM_RUNS \
        -c /packages/apps/fpga/Questa/questa_fe/bin \
        --id "sigmoid" \
        --model "models--casperhansen--llama-3.3-70b-instruct-awq" \
        --tokenizer "meta-llama/Llama-3.3-70B-Instruct" \
        --quantize \
        -m \
        --temperature_function "sigmoid" \
        --max_iterations 20 \
        --max_valid_iter 10 \
        -o /scratch/$USER/runs/${DATA_POINT}_sigmoid_$RUN \
        2>&1 | tee /scratch/$USER/runs/${DATA_POINT}_sigmoid_$RUN/${DATA_POINT}_sigmoid_$RUN.log

elif [ "$RUN_TYPE" == "batch" ]; then

    python /scratch/$USER/runs/evaluations/evaluate_methodology6.py \
        -d $REPO_DIR/data_points/$DATA_POINT \
        -g $NUM_RUNS \
        -c /packages/apps/fpga/Questa/questa_fe/bin \
        --id "batch" \
        --model "models--casperhansen--llama-3.3-70b-instruct-awq" \
        --tokenizer "meta-llama/Llama-3.3-70B-Instruct" \
        --quantize \
        -m \
        --max_iterations 20 \
        --max_valid_iter 10 \
        -b 5 \
        -o /scratch/$USER/runs/${DATA_POINT}_batch_$RUN \
        2>&1 | tee /scratch/$USER/runs/${DATA_POINT}_batch_$RUN/${DATA_POINT}_batch_$RUN.log

elif [ "$RUN_TYPE" == "testplan" ]; then

    python /scratch/$USER/runs/evaluations/evaluate_methodology6.py \
        -d $REPO_DIR/data_points/$DATA_POINT \
        -g $NUM_RUNS \
        -c /packages/apps/fpga/Questa/questa_fe/bin \
        --id "testplan" \
        --model "models--casperhansen--llama-3.3-70b-instruct-awq" \
        --tokenizer "meta-llama/Llama-3.3-70B-Instruct" \
        --quantize \
        -m \
        --max_iterations 20 \
        --max_valid_iter 10 \
        --testplan \
        -o /scratch/$USER/runs/${DATA_POINT}_testplan_$RUN \
        2>&1 | tee /scratch/$USER/runs/${DATA_POINT}_testplan_$RUN/${DATA_POINT}_testplan_$RUN.log

else

    echo "$RUN_TYPE is not a valid type of run."

fi 

deactivate
