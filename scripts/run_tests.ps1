# Run pytest tests with proper PYTHONPATH
$env:PYTHONPATH = "$PWD"
pytest -q
