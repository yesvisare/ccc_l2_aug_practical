# Run the M5.1 Incremental Indexing API
# Usage: .\scripts\run_api.ps1

$env:PYTHONPATH = $PWD
Write-Host "Starting M5.1 Incremental Indexing API..."
Write-Host "PYTHONPATH set to: $env:PYTHONPATH"
uvicorn app:app --reload --host 0.0.0.0 --port 8000
