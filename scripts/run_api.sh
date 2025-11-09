#!/bin/bash
# Run the FastAPI application with auto-reload
# Usage: bash scripts/run_api.sh

echo -e "\033[32mStarting FastAPI application...\033[0m"

# Set Python path to include src directory
export PYTHONPATH="$PWD/src:$PWD"

# Run uvicorn
uvicorn app:app --reload --host 0.0.0.0 --port 8000
