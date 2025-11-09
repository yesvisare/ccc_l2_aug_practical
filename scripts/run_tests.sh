#!/bin/bash
export PYTHONPATH="$PWD/src:$PWD"
python3 -m pytest tests/ -q
