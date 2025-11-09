# Windows PowerShell script to run the FastAPI application
# Sets PYTHONPATH to include src/ for package discovery

$env:PYTHONPATH = "$PWD"
Write-Host "Starting Compliance & Audit Logging API..."
Write-Host "PYTHONPATH set to: $env:PYTHONPATH"
uvicorn app:app --reload
