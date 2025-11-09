#!/bin/bash
# Run FastAPI server for M5.3 Data Quality & Validation
# Sets PYTHONPATH to project root and starts uvicorn with hot reload

set -e

# Set PYTHONPATH to include src directory
export PYTHONPATH="$PWD/src:$PWD"

echo "Starting M5.3 Data Quality API..."
echo "API Docs: http://localhost:8000/docs"
echo ""

# Start uvicorn with reload for development
uvicorn app:app --reload --host 0.0.0.0 --port 8000
