#!/bin/bash
# Run validation demo for M5.3 Data Quality & Validation
# Sets PYTHONPATH and runs validation on example data

set -e

# Set PYTHONPATH to include src directory
export PYTHONPATH="$PWD/src:$PWD"

echo "Running M5.3 Data Quality Validation Demo..."
echo ""

# Run validation using Python
python3 << 'EOF'
import json
from m5_3_data_quality import (
    ChunkQualityScorer,
    DuplicateDetector,
    filter_low_quality_chunks,
    remove_duplicates,
    ChunkMetadata
)

# Load example data
with open('example_data.json', 'r') as f:
    data = json.load(f)

chunks_data = data['chunks']

# Prepare chunks for validation
chunks = [
    (chunk['chunk_id'], chunk['text'],
     ChunkMetadata(**chunk['metadata']) if chunk['metadata'] else None)
    for chunk in chunks_data
]

print(f'Input: {len(chunks)} chunks')

# Quality filtering
passed_chunks, scores = filter_low_quality_chunks(chunks, min_score=70.0)
pass_rate = len(passed_chunks) / len(chunks) * 100
print(f'After quality filter: {len(passed_chunks)} ({pass_rate:.1f}% pass rate)')

# Deduplication
unique_ids = remove_duplicates(passed_chunks, threshold=0.85)
dedup_rate = (len(passed_chunks) - len(unique_ids)) / len(passed_chunks) * 100 if passed_chunks else 0
print(f'After deduplication: {len(unique_ids)} ({dedup_rate:.1f}% dedup rate)')

print(f'\nFinal validated chunks: {len(unique_ids)} / {len(chunks)}')
print(f'Overall pass rate: {len(unique_ids) / len(chunks) * 100:.1f}%')
EOF
