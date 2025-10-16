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
│       └── questa/      # QuestaSim project files and Makefiles
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
- **Simulator** (choose one or both):
  - [Verilator](https://verilator.org/) (open-source, recommended for getting started)
  - [QuestaSim](https://www.mentor.com/products/fv/questa/) (commercial)
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

- See `scripts/run_job.sh` and `scripts/setup_configs.sh` for examples on how to configure and run the framework. You can also see `llm_verif/README.md` for a more detailed list of command line args to run the tools. Or, run:
```bash
llm_verif --help
``` 

## Data Points

- Each subdirectory in `data/` represents a hardware module with its own simulation setup.

---

For more details on running jobs and troubleshooting, see [llm_verif/README.md](llm_verif/README.md).

