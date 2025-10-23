#!/bin/bash

TEMPERATURE_FUNCTIONS=("constant" "logarithmic" "capped_sigmoid")
REMOVE_POLLUTED_CONTEXT=(1 0)
BATCH_SIZES=(1 5)
TESTPLAN=(1 0)


mkdir -p configs

for func in "${TEMPERATURE_FUNCTIONS[@]}"; do
  for remove_polluted_context in "${REMOVE_POLLUTED_CONTEXT[@]}"; do
    for batch in "${BATCH_SIZES[@]}"; do
      for testplan in "${TESTPLAN[@]}"; do

        FILE="configs/base_env_${func}_${remove_polluted_context}_${batch}_${testplan}.env"
        echo "Generating $FILE"

        cat > "$FILE" <<EOF
OPENAI_API_KEY=test-key
API_KEY=test-key
BASE_URL=http://localhost:8000/v1
BACKEND=openai
SIMULATOR=verilator
COMPILER=/home/slowe8/verilator/bin
MODEL=casperhansen/llama-3.3-70b-instruct-awq
MERGE_COVERAGE=1
SIM_RUNS=5
MAX_ITERATIONS=3
MAX_VALID_ITER=2
TEMPERATURE_FUNCTION=${func}
BATCH_SIZE=${batch}
TESTPLAN=${testplan}
REMOVE_POLLUTED_CONTEXT=${remove_polluted_context}
RUNS=2
EOF
      done
    done
  done
done
