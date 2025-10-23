# Spec2Cov: An Agentic Framework for Code Coverage Closure of Digital Hardware Designs

This repository contains scripts, data, and workflows for generating and evaluating verification datasets using Large Language Models (LLMs) for hardware design verification tasks. The project is designed to automate the process of generating testbenches, running simulations, and collecting coverage data for various hardware modules.

## Table of Contents

- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Environment Setup](#environment-setup)
  - [Model Access](#model-access)
- [Usage](#usage)
  - [Running Testbench Generation Jobs](#running-testbench-generation-jobs)
  - [Simulation and Coverage](#simulation-and-coverage)
- [Scripts](#scripts)
- [Data Points](#data-points)
- [Contributing](#contributing)
- [License](#license)

---

## Project Structure

```
llm_verif/
├── data/                # Hardware modules and their simulation setups
│   └── <module>/        # Each module (e.g., oh, dpretet_axi-crossbar)
├── llm_veirf/           # Source files
│   ├── __init.py__
│   ├── llm_verif.py
│   ├── chatgpt_chat.py
│   └── ...
├── tests/               # Project tests (not up to date)
├── scripts/             # Some relevant project scripts (also not up to date)
├── README.md            # This file
└── ...
```

- **data/**: Contains hardware modules and their simulation environments.
- **llm_verif/**: Contains source code for LLM-based testbench generation and evaluation.
- **scripts/**: Contains job scripts for running experiments and batch jobs.

## Getting Started

### Prerequisites

- Access to a Linux environment (e.g., Sol cluster).
- **Simulator**:
  - [Verilator](https://verilator.org/) (open-source, **primary supported simulator**)
  - [QuestaSim](https://www.mentor.com/products/fv/questa/) (commercial, also supported)
- [Huggingface](https://huggingface.co/) account for model access (if using local models).
- Python 3.11 or later.

### Environment Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/advent-lab/llm-verif
   pip install -e llm_verif/
   ```

2. **Install Verilator (for open-source simulator support):**

   ```bash
   # Install prerequisites
   sudo apt-get install git perl python3 make autoconf g++ flex bison ccache
   sudo apt-get install libgoogle-perftools-dev numactl perl-doc
   sudo apt-get install libfl2 libfl-dev zlibc zlib1g zlib1g-dev

   # Clone and build Verilator
   git clone https://github.com/verilator/verilator
   cd verilator
   autoconf
   ./configure
   make -j$(nproc)
   ```

   After building, note the path to the Verilator binary (e.g., `/path/to/verilator/bin/verilator`). You'll pass this to the framework using `--compiler /path/to/verilator/bin/verilator`.

### Model Access

1. **Request access to Meta's Llama3.1:**
   - Visit [Llama-3.1-8B-Instruct](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct) and request access.

2. **Generate a Huggingface Access Token:**
   - Go to your Huggingface account settings > Access Tokens.

3. **Login on the cluster:**
   ```bash
   huggingface-cli login
   # Paste your access token when prompted
   ```

## Usage

### Running Testbench Generation Jobs

**Local/Interactive Mode:**
```bash
llm_verif --help  # See all available options
```

**SLURM Cluster Mode (Recommended for Large-Scale Experiments):**

For running vLLM-based experiments on SLURM clusters with automatic server management:

1. Generate configuration files:
   ```bash
   bash scripts/setup_vllm_configs.sh
   ```

2. Edit `scripts/run_vllm_design.sh` to select designs and configurations

3. Submit the job:
   ```bash
   sbatch scripts/run_vllm_design.sh
   ```

The SLURM script automatically:
- Creates a standalone vLLM virtual environment (avoids dependency conflicts)
- Starts vLLM inference server with optimal settings
- Runs experiments across multiple designs and configurations
- Manages cleanup and result archival

See `llm_verif/README.md` for detailed command-line options and configuration details. 

## Data Points

- Each subdirectory in `data/` represents a hardware module with its own simulation setup.

---

For more details on running jobs and troubleshooting, see [llm_verif/README.md](llm_verif/README.md).

