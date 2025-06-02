# LLM Verification Dataset

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
llm_verif_dataset/
├── data_points/         # Hardware modules and their simulation setups
│   └── <module>/        # Each module (e.g., oh, dpretet_axi-crossbar)
│       └── questa/      # QuestaSim project files and Makefiles
├── llm/                 # LLM-related scripts, requirements, and configs
│   ├── requirements.in
│   ├── requirements.txt
│   ├── build_llm_venv.sh
│   └── scripts/         # Job scripts for running LLM-based workflows
├── README.md            # This file
└── ...
```

- **data_points/**: Contains hardware modules and their simulation environments.
- **llm/**: Contains scripts and requirements for LLM-based testbench generation and evaluation.
- **llm/scripts/**: Contains job scripts for running experiments and batch jobs.

## Getting Started

### Prerequisites

- Access to a Linux environment (e.g., Sol cluster).
- [QuestaSim](https://www.mentor.com/products/fv/questa/) installed and accessible.
- [Huggingface](https://huggingface.co/) account for model access.
- Python 3.11 or later.

### Environment Setup

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd llm_verif_dataset
   ```

2. **Set up the Python environment:**
   - On the Sol cluster, run:
     ```bash
     cd llm
     source build_llm_venv.sh
     ```
   - This script creates a virtual environment (`llm_venv`) and installs all required dependencies.

3. **(Optional) Manual setup:**
   ```bash
   cd llm
   python3 -m venv ~/llm_venv
   source ~/llm_venv/bin/activate
   pip install --upgrade pip
   pip install pip-tools
   pip-sync requirements.txt
   deactivate
   ```

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

- Example usage of a job script:
  ```bash
  llm/scripts/method6_job.sh <repo_path> <datapoint_name> <NUM_RUNS> <RUN_ID>
  ```
- To run as a batch job:
  ```bash
  sbatch llm/scripts/method6_job.sh <repo_path> <datapoint_name> <NUM_RUNS> <RUN_ID>
  ```

- See `llm/README.md` for more details and example scripts.

### Simulation and Coverage

- Each datapoint contains a `questa/Makefile` for compiling and simulating the hardware design.
- Example:
  ```bash
  cd data_points/oh/questa
  make all
  ```
- This will:
  - Create the simulation library
  - Compile the design files
  - Run the simulation and generate coverage reports

## Scripts

- **llm/build_llm_venv.sh**: Automates environment setup.
- **llm/scripts/**: Contains job scripts for running LLM-based workflows and experiments.

## Data Points

- Each subdirectory in `data_points/` represents a hardware module with its own simulation setup.
- Makefiles are provided for easy simulation and coverage collection.

---

For more details on running jobs and troubleshooting, see [llm/README.md](llm/README.md).

