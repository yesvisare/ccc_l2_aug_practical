#!/bin/bash
# Run the FastAPI application
# Usage: ./scripts/run_api.sh

export PYTHONPATH="$PWD"
echo "Starting FastAPI server..."
echo "API documentation will be available at: http://localhost:8000/docs"
echo ""

uvicorn app:app --reload --host 0.0.0.0 --port 8000
