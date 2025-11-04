#!/bin/bash

# Define the parent directory
parent_dir="."

# Loop through each subdirectory in the parent directory
for dir in "$parent_dir"/*/; do
    # Run git rm --cached for each subdirectory
    git rm --cached "$dir" -r
    echo "Removed $dir from cache"
done
