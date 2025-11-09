#!/bin/bash
export PYTHONPATH="$PWD/src"
uvicorn app:app --reload
