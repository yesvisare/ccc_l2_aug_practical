# Run the FastAPI application with auto-reload
# Usage: powershell scripts/run_api.ps1

Write-Host "Starting FastAPI application..." -ForegroundColor Green

# Set Python path to include src directory
$env:PYTHONPATH = "$PWD/src;$PWD"

# Run uvicorn
uvicorn app:app --reload --host 0.0.0.0 --port 8000
