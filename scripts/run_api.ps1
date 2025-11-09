# Run the FastAPI server with auto-reload
# Usage: .\scripts\run_api.ps1

$env:PYTHONPATH = "$PWD/src;$PWD"
Write-Host "Starting FastAPI server..."
Write-Host "API docs at: http://localhost:8000/docs"
Write-Host "Press Ctrl+C to stop"
Write-Host ""
uvicorn app:app --reload
