#!/bin/bash
# Run the FastAPI application with auto-reload
export PYTHONPATH="$PWD"
uvicorn app:app --reload --host 0.0.0.0 --port 8080
