# Run pytest for M5.3 Data Quality & Validation
# Sets PYTHONPATH and runs all tests

$ErrorActionPreference = "Stop"

# Set PYTHONPATH to include src directory
$env:PYTHONPATH = "$PWD/src;$PWD"

Write-Host "Running M5.3 Data Quality Tests..." -ForegroundColor Green
Write-Host ""

# Run pytest with verbose output
pytest tests/ -v --tb=short
