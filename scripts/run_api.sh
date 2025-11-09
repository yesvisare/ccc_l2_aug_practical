#!/bin/bash
# Run the FastAPI server with auto-reload
# Usage: ./scripts/run_api.sh

export PYTHONPATH="$PWD/src:$PWD"
echo "Starting FastAPI server..."
echo "API docs at: http://localhost:8000/docs"
echo "Press Ctrl+C to stop"
echo ""
uvicorn app:app --reload
