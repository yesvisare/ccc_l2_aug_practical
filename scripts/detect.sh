#!/bin/bash
# Detect changes in document corpus
# Usage: ./scripts/detect.sh [documents_dir]
# Example: ./scripts/detect.sh example_documents

DOCS_DIR="${1:-example_documents}"

export PYTHONPATH="$PWD"
echo "Detecting changes in: $DOCS_DIR"
python -m m5_1_incremental_indexing.core detect "$DOCS_DIR"
