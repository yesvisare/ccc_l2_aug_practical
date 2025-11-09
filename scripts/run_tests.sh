#!/bin/bash
# Unix shell script to run tests with proper PYTHONPATH

export PYTHONPATH="$PWD/src:$PYTHONPATH"
echo "Running tests for Module 6.1: PII Detection & Redaction"
echo "PYTHONPATH: $PYTHONPATH"
echo ""

pytest tests/ -v
