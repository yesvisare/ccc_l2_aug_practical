# Run the FastAPI application
# Usage: .\scripts\run_api.ps1

$env:PYTHONPATH = "$PWD"
Write-Host "Starting FastAPI server..." -ForegroundColor Cyan
Write-Host "API documentation will be available at: http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host ""

uvicorn app:app --reload --host 0.0.0.0 --port 8000
