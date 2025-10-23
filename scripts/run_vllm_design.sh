#!/bin/bash

#SBATCH -N 1            # number of nodes
#SBATCH -c 32           # number of cores
#SBATCH --mem=64G
#SBATCH -t 0-12:00:00   # 12 hours runtime
#SBATCH -G a100:2       # 2x A100 GPUs for tensor parallelism
#SBATCH -C a100_80      # 80GB A100s
#SBATCH -p general      # partition
#SBATCH -q public       # QOS
#SBATCH -o slurm.%j.out # file to save job's STDOUT (%j = JobId)
#SBATCH -e slurm.%j.err # file to save job's STDERR (%j = JobId)
#SBATCH --mail-type=ALL # Send an e-mail when a job starts, stops, or fails
#SBATCH --mail-user="%u@asu.edu"
#SBATCH --export=LM_LICENSE_FILE=27006@en4228283l.cidse.dhcp.asu.edu

echo "Job started at: $(date)"
echo "LM_LICENSE_FILE: $LM_LICENSE_FILE"

# Configuration
VLLM_PORT=8000
VLLM_API_KEY="test-key"
MODEL_NAME="casperhansen/llama-3.3-70b-instruct-awq"
TENSOR_PARALLEL_SIZE=2  # Match number of GPUs requested

# Designs to process
designs=(
  cvdp_agentic_sorter
  pooling
  sha1_top
)

# Path to generated base_env configs
REPO_DIR="/home/local/ASURITE/slowe8/thesis/llm_verif_dataset"
config_dir="$REPO_DIR/configs"
base_envs=(${config_dir}/base_env_constant_1_5_1.env)

# Setup working directory
SCRATCH_DIR="/scratch/$USER/vllm_runs_${SLURM_JOB_ID}"
mkdir -p "$SCRATCH_DIR"
cd "$SCRATCH_DIR"

echo "Working directory: $SCRATCH_DIR"

# ============================================================================
# Step 1: Create standalone vLLM virtual environment
# ============================================================================
echo ""
echo "=================================================="
echo "Creating standalone vLLM virtual environment..."
echo "=================================================="

VLLM_VENV_DIR="$SCRATCH_DIR/vllm-venv"
python3 -m venv "$VLLM_VENV_DIR"
source "$VLLM_VENV_DIR/bin/activate"

# Install vLLM and dependencies
pip install --upgrade pip
pip install vllm

echo "vLLM installation complete"
pip list | grep vllm

# ============================================================================
# Step 2: Start vLLM inference server in background
# ============================================================================
echo ""
echo "=================================================="
echo "Starting vLLM inference server..."
echo "=================================================="

VLLM_LOG="$SCRATCH_DIR/vllm_server.log"

vllm serve "$MODEL_NAME" \
    --api-key "$VLLM_API_KEY" \
    --port "$VLLM_PORT" \
    --tensor-parallel-size "$TENSOR_PARALLEL_SIZE" \
    --gpu-memory-utilization 0.85 \
    --quantization awq \
    --max-model-len 32766 \
    > "$VLLM_LOG" 2>&1 &

VLLM_PID=$!
echo "vLLM server started with PID: $VLLM_PID"
echo "Log file: $VLLM_LOG"

# Wait for vLLM server to be ready
echo "Waiting for vLLM server to initialize..."
max_wait=300  # 5 minutes
waited=0
while ! curl -s "http://localhost:$VLLM_PORT/v1/models" > /dev/null 2>&1; do
    sleep 5
    waited=$((waited + 5))
    if [ $waited -ge $max_wait ]; then
        echo "ERROR: vLLM server failed to start within $max_wait seconds"
        echo "Last 50 lines of vLLM log:"
        tail -50 "$VLLM_LOG"
        kill $VLLM_PID 2>/dev/null
        exit 1
    fi
    echo "  Still waiting... ($waited seconds elapsed)"
done

echo "vLLM server is ready!"
curl -s "http://localhost:$VLLM_PORT/v1/models" | head -20

# Deactivate vLLM venv before switching to llm_verif venv
deactivate

# ============================================================================
# Step 3: Setup llm_verif environment
# ============================================================================
echo ""
echo "=================================================="
echo "Setting up llm_verif environment..."
echo "=================================================="

# Create and activate llm_verif venv
LLM_VENV_DIR="$SCRATCH_DIR/venv"
python3 -m venv "$LLM_VENV_DIR"
source "$LLM_VENV_DIR/bin/activate"

pip install --upgrade pip
pip install -e "$REPO_DIR/llm_verif"

echo "llm_verif installation complete"

# Load simulator module
module load bittware/questa-23.4
export LM_LICENSE_FILE=27006@en4228283l.cidse.dhcp.asu.edu

# ============================================================================
# Step 4: Run llm_verif experiments
# ============================================================================
echo ""
echo "=================================================="
echo "Running llm_verif experiments..."
echo "=================================================="

run_job() {
    design="$1"
    base_env="$2"

    echo ""
    echo "=========================================="
    echo "Running tests for design: $design"
    echo "=========================================="

    # Absolute path to design directory
    design_path="$REPO_DIR/data/$design"

    # Extract config name
    config_name=$(basename "$base_env" .env | cut -d'_' -f3-)

    # Create WORK_DIR for this config+design combo
    WORK_DIR="$SCRATCH_DIR/results/$design/$config_name"
    mkdir -p "$WORK_DIR"

    # Build full .env file
    cp "$base_env" "$WORK_DIR/.env"
    echo "WORK_DIR=$WORK_DIR" >> "$WORK_DIR/.env"
    echo "DESIGN=$design_path" >> "$WORK_DIR/.env"
    echo "ID=\"vllm $design $config_name trial\"" >> "$WORK_DIR/.env"

    # Run llm_verif
    echo "→ Running config $config_name for $design"
    echo "  Work directory: $WORK_DIR"
    echo "  Config file: $WORK_DIR/.env"

    llm_verif --dotenv_path "$WORK_DIR/.env" --backend "openai" 2>&1 | tee "$WORK_DIR/${design}_run.log"

    local exit_code=${PIPESTATUS[0]}
    if [ $exit_code -eq 0 ]; then
        echo "✓ Successfully completed: $design with config $config_name"
    else
        echo "✗ Failed: $design with config $config_name (exit code: $exit_code)"
    fi
}

# Run experiments for each design and config
for design in "${designs[@]}"; do
    for base_env in "${base_envs[@]}"; do
        run_job "$design" "$base_env"
    done
done

# ============================================================================
# Step 5: Cleanup
# ============================================================================
echo ""
echo "=================================================="
echo "Cleaning up..."
echo "=================================================="

# Deactivate llm_verif venv
deactivate

# Stop vLLM server
if kill -0 $VLLM_PID 2>/dev/null; then
    echo "Stopping vLLM server (PID: $VLLM_PID)..."
    kill $VLLM_PID
    wait $VLLM_PID 2>/dev/null
    echo "vLLM server stopped"
else
    echo "vLLM server already stopped"
fi

# Copy results to permanent storage
RESULTS_DIR="$REPO_DIR/results/vllm_run_${SLURM_JOB_ID}"
mkdir -p "$RESULTS_DIR"
cp -r "$SCRATCH_DIR/results/"* "$RESULTS_DIR/"
echo "Results copied to: $RESULTS_DIR"

echo ""
echo "=================================================="
echo "Job completed at: $(date)"
echo "=================================================="
