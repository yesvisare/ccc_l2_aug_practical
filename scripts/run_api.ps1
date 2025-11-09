# Windows PowerShell script to run the FastAPI application
# Sets PYTHONPATH to project root and starts uvicorn in reload mode

$env:PYTHONPATH = $PWD
Write-Host "Starting PII Detection & Redaction API service..."
Write-Host "PYTHONPATH set to: $PWD"
Write-Host "API docs will be available at: http://localhost:8000/docs"
Write-Host ""

uvicorn app:app --reload --host 0.0.0.0 --port 8000
