#!/bin/bash
export PYTHONPATH="$PWD/src:$PWD"
export SKIP_INTEGRATION_TESTS=true
python3 -m pytest tests/ -v
