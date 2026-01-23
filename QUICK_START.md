# Project Setup and Quick Start

## Prerequisites

- QuestaSim or Verilator installed
- Python 3.8+
- OpenAI API key (or other LLM provider)

## Installation

**No package installation required** - the framework uses direct imports via path manipulation.

```bash
# 1. Create Python environment (skip if exists)
mamba create -n lg_venv -c conda-forge pip -y # SOL-specific

# 2. Activate environment
module load mamba/latest
module load bittware/questa-23.4
source activate lg_venv

# 3. Install Python dependencies
pip install -r requirements.txt
```

## Configuration

Create or copy an environment file:

```bash
# Use example config
cp .env.example .env
```

Required environment variables:
- `COMPILER` - Path to simulator binaries
- `SIMULATOR` - Simulator type (questasim or verilator)
- `DESIGN_NAME` - Design to verify (must match directory in data/)
- `OPENAI_API_KEY` - Your API key
- `DASHBOARD_PATH` - Absolute path to dashboard.json

See existing configs in `configs/` for examples.

## Running the Agent

```bash
# Use default .env file in project root
python run_agent.py

# Specify custom config file
python run_agent.py -e configs/questasim.env
python run_agent.py --env-file path/to/custom.env

# Validate config without running
python run_agent.py --validate-only

# Get help
python run_agent.py --help
```

## Troubleshooting


