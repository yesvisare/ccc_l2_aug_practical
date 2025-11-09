# Run the FastAPI server with auto-reload
# Usage: .\scripts\run_api.ps1

$env:PYTHONPATH = "$PWD"
Write-Host "Starting Module 7.3 API server..."
Write-Host "PYTHONPATH=$env:PYTHONPATH"

uvicorn app:app --reload --host 0.0.0.0 --port 8080
