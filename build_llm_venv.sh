#!/bin/bash

# Check if llm_venv exists
if [ -d ~/llm_venv/ ]; then
    echo "llm_venv exists. Syncing with requirements.txt..."
    source ~/llm_venv/bin/activate
    pip install --upgrade pip
    pip install pip-tools
    pip-sync requirements.txt
else
    echo "llm_venv does not exist. Creating and installing requirements..."
    module load mamba
    source activate scicomp
    python3 -m venv ~/llm_venv
    deactivate
    source ~/llm_venv/bin/activate
    pip install --upgrade pip
    pip install pip-tools
    pip-sync requirements.txt
fi

echo "Environment setup complete."
