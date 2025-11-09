#!/bin/bash
# Run FastAPI server with RBAC endpoints
# Usage: ./scripts/run_api.sh

export PYTHONPATH="$PWD/src:$PWD"
uvicorn app:app --reload --host 0.0.0.0 --port 8000
