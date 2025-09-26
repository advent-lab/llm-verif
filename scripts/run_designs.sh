#!/bin/bash

MAX_JOBS=20

designs=(
  # cvdp_agentic_alu
  # cvdp_agentic_caesar_cipher
  # cvdp_agentic_cic_decimator
  # cvdp_agentic_cont_adder
  # cvdp_agentic_door_lock
  # cvdp_agentic_dual_port_memory
  # cvdp_agentic_fixed_arbiter
  # cvdp_agentic_memory_scheduler
  # cvdp_agentic_multiplexer
  # cvdp_agentic_rgb_color_space_conversion
  # cvdp_agentic_sorter
  # cvdp_agentic_ttc_lite
	# cvdp_agentic_spi_complex_mult
	# cvdp_agentic_poly_interpolator
	# cvdp_agentic_lfsr
	# cvdp_agentic_async_fifo_compute_ram_application
	sha1_top
	chacha_top
	activation
	cryptech_uart
	fifo
	float_adder
	float_multiplier
	pooling
	simple_mat_mul
	trng_top
	vndecorrelator
)

source llm_verif_dataset/venv/bin/activate
pip uninstall llm_verif -y
pip install -e llm_verif_dataset

# Path to your generated base_env configs
config_dir="configs"
base_envs=(${config_dir}/base_env_*.env)

job_count=0

run_job() {
	design="$1"
	base_env="$2"

	echo "Running tests for design: $design"

	# Absolute path to design directory
	design_path="/home/local/ASURITE/slowe8/thesis/llm_verif_dataset/data/$design"

	# Extract config name: base_env_constant_0.3_1.env → constant_0.3_1
	config_name=$(basename "$base_env" .env | cut -d'_' -f3-)

	# Create WORK_DIR for this config+design combo
	WORK_DIR="results/$design/$config_name"
	mkdir -p "$WORK_DIR"

	# Build full .env file
	cp "$base_env" "$WORK_DIR/.env"
	echo "WORK_DIR=$WORK_DIR" >> "$WORK_DIR/.env"
	echo "DESIGN=$design_path" >> "$WORK_DIR/.env"
	echo "ID=\"cvdp $design $config_name trial\"" >> "$WORK_DIR/.env"

	# Run and log output
	echo "→ Running config $config_name for $design"
	llm_verif --dotenv_path "$WORK_DIR/.env" > "$WORK_DIR/${design}.log" 2>&1
}

for design in "${designs[@]}"; do
	for base_env in "${base_envs[@]}"; do
		run_job "$design" "$base_env" &
		((job_count++))
		if (( job_count % MAX_JOBS == 0 )); then
			echo "Waiting for batch of $MAX_JOBS to complete..."
			wait
		fi
	done
done

