#!/bin/bash
export PYTHONPATH="$PWD/src:$PWD"
uvicorn app:app --reload
