#!/bin/bash
# Unix shell script to run the FastAPI application
# Sets PYTHONPATH to project root and starts uvicorn in reload mode

export PYTHONPATH="$PWD"
echo "Starting PII Detection & Redaction API service..."
echo "PYTHONPATH set to: $PWD"
echo "API docs will be available at: http://localhost:8000/docs"
echo ""

uvicorn app:app --reload --host 0.0.0.0 --port 8000
