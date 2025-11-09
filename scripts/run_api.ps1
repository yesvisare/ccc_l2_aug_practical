# M5.4 Vector Index Management - API Server Launcher (Windows PowerShell)
#
# Usage: .\scripts\run_api.ps1
#
# This script sets up the Python path and launches the FastAPI server.

# Set PYTHONPATH to include src/ directory
$env:PYTHONPATH = "$PWD/src"

Write-Host "=== M5.4 Vector Index Management API ===" -ForegroundColor Green
Write-Host "PYTHONPATH: $env:PYTHONPATH" -ForegroundColor Cyan
Write-Host "Starting uvicorn server..." -ForegroundColor Cyan
Write-Host ""

# Launch uvicorn with hot reload
uvicorn app:app --reload --host 0.0.0.0 --port 8000
