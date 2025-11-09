# Windows PowerShell script to run the FastAPI application
# Sets PYTHONPATH to include src/ and starts uvicorn in reload mode

$env:PYTHONPATH = "$PWD;$PWD\src"
Write-Host "Starting PII Detection & Redaction API service..."
Write-Host "PYTHONPATH set to: $env:PYTHONPATH"
Write-Host "API docs will be available at: http://localhost:8000/docs"
Write-Host ""

uvicorn app:app --reload
