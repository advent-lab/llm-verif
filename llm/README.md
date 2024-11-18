# How to run a testbench generation job

## 1. Get access to the model
We are using Meta's Llama3.1 for our experiments which is a gated repo and requires approval from the maintainers for you to get access. Go to https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct to request access.

## 2. Create an Access Token to access the model from the Sol cluster
To use the model on the Sol cluster, you need to generate an Access Token in Huggingface. Go to Settings > Access Tokens to generate one.

## 3. Login to Huggingface on the Sol cluster using huggingface-cli
Log into the Sol cluster (it can be a lightweight shell) and run: `huggingface-cli login`
Then, paste your Huggingface Access Token where it says "Token:"
You should see a message saying that you were successfully logged in if everything worked correctly. Others have had issues with this working correctly, so let someone know if you are having issues.

## 4. Build the Python environment
Run the following code on the Sol cluster:
```bash
cd ~
module load mamba
source activate scicomp
python -m venv llm_venv
deactivate
source llm_venv/bin/activate
pip install -r <cloned repo path>/llm/requirements.txt
deactivate
```
This code creates the virtual python environment that will be envoked by the scripts

## 5. Try to run the job scripts!

In the methods scripts, you can run them interactively or in batch. If you want to run them interactively to debug, make sure the python call in the script is going to stdout. Otherwise, uncomment the pipe at the end of the line to make it go to a log file.

The scripts take the number of conversations, or runs, as a third argument.
The scripts take a run id as a fourth argument, which will differentiate the directory names for batched runs. 
I have an example script called run_parallel_runs.sh which shows how this works.

Example usage of each script:
```bash
<cloned repo path>/llm/scripts/method6_job.sh <path to repo> <name of a datapoint> <NUMBER OF RUNS> <RUN id>
```
You can also submit them using sbatch if you want them to run as a job on the Sol cluter
```bash
sbatch scripts/module6_job.sh <path to repo> <name of a datapoint> <NUMBER OF RUNS> <RUN id>
```

