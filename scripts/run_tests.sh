#!/bin/bash
# Run pytest for M5.3 Data Quality & Validation
# Sets PYTHONPATH and runs all tests

set -e

# Set PYTHONPATH to include src directory
export PYTHONPATH="$PWD/src:$PWD"

echo "Running M5.3 Data Quality Tests..."
echo ""

# Run pytest with verbose output
pytest tests/ -v --tb=short
