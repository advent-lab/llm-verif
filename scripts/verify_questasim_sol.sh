#!/bin/bash

echo "==================================================="
echo "QuestaSim License & Availability Check for SOL env"
echo "==================================================="

# Load required modules
echo -e "\n[1/4] Loading modules..."
module load mamba/latest
module load bittware/questa-23.4

if [ $? -ne 0 ]; then
    echo "❌ ERROR: Failed to load modules"
    exit 1
fi
echo "✓ Modules loaded successfully"

# Set license server
echo -e "\n[2/4] Setting license server..."
export LM_LICENSE_FILE=27006@en4228283l.scai.dhcp.asu.edu
echo "✓ License server: $LM_LICENSE_FILE"

# Check if vsim command exists
echo -e "\n[3/4] Checking QuestaSim installation..."
if command -v vsim &> /dev/null; then
    echo "✓ vsim found at: $(which vsim)"
    vsim -version | head -5
else
    echo "❌ ERROR: vsim command not found"
    exit 1
fi

# Test license connectivity
echo -e "\n[4/4] Testing license server connectivity..."
echo "Running: vsim -c -do 'quit -f'"
timeout 10s vsim -c -do "quit -f" &> /tmp/vsim_test.log

if [ $? -eq 0 ]; then
    echo "✓ License server is accessible and working!"
    echo -e "\n================================================"
    echo "✅ QuestaSim is ready to use"
    echo "================================================"
else
    echo "❌ ERROR: License server test failed"
    echo "Check the log output below:"
    cat /tmp/vsim_test.log
    echo -e "\nPossible issues:"
    echo "  - License server is down"
    echo "  - Network connectivity issues"
    echo "  - License expired or not available"
    exit 1
fi
