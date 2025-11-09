# Run regression testing CI/CD tests
# Usage: .\scripts\run_tests.ps1

$env:PYTHONPATH = "$PWD"
Write-Host "Running tests with pytest..." -ForegroundColor Cyan
pytest -v tests/

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✓ All tests passed!" -ForegroundColor Green
} else {
    Write-Host "`n✗ Some tests failed" -ForegroundColor Red
    exit $LASTEXITCODE
}
