#!/bin/bash
# Run pytest tests with proper PYTHONPATH
export PYTHONPATH="$PWD"
pytest -q
