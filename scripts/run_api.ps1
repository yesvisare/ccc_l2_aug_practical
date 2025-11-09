# Run FastAPI server for M5.3 Data Quality & Validation
# Sets PYTHONPATH to project root and starts uvicorn with hot reload

$ErrorActionPreference = "Stop"

# Set PYTHONPATH to include src directory
$env:PYTHONPATH = "$PWD/src;$PWD"

Write-Host "Starting M5.3 Data Quality API..." -ForegroundColor Green
Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""

# Start uvicorn with reload for development
uvicorn app:app --reload --host 0.0.0.0 --port 8000
