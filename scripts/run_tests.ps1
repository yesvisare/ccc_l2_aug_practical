# Windows PowerShell script to run tests with proper PYTHONPATH

$env:PYTHONPATH = "$PWD\src;$env:PYTHONPATH"
Write-Host "Running tests for Module 6.1: PII Detection & Redaction"
Write-Host "PYTHONPATH: $env:PYTHONPATH"
Write-Host ""

pytest tests/ -v
