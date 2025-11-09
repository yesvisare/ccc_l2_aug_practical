#!/bin/bash
# Run the M5.1 Incremental Indexing API
# Usage: ./scripts/run_api.sh

export PYTHONPATH="$PWD"
echo "Starting M5.1 Incremental Indexing API..."
echo "PYTHONPATH set to: $PYTHONPATH"
uvicorn app:app --reload --host 0.0.0.0 --port 8000
