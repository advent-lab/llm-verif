#!/bin/bash

# Define the parent directory
parent_dir="data_points"

# Loop through each subdirectory in the parent directory
for dir in "$parent_dir"/*/; do
    # Run git rm --cached for each subdirectory
    git rm --cached "$dir"
    echo "Removed $dir from cache"
done
