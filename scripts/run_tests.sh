#!/bin/bash
export PYTHONPATH="$PWD/src:$PWD"
pytest -q
