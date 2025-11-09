# Run pytest tests
# Usage: .\scripts\run_tests.ps1

$env:PYTHONPATH = "$PWD"
Write-Host "Running tests..."
Write-Host "PYTHONPATH=$env:PYTHONPATH"

pytest -q
