#!/bin/bash
# Run the demo pipeline
# Usage: ./scripts/run_demo.sh

export PYTHONPATH="$PWD/src:$PWD"
echo "Running M5.2 Data Pipelines Demo..."
echo ""
python -c "from m5_2_data_pipelines.core import run_incremental_refresh_pipeline; from m5_2_data_pipelines.config import DATA_DIR, CHECKSUM_FILE, get_clients; clients = get_clients(); result = run_incremental_refresh_pipeline(DATA_DIR, CHECKSUM_FILE, clients['openai'], clients['pinecone']); print('\nDemo complete!')"
