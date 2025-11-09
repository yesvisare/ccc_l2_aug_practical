# Run FastAPI server with RBAC endpoints
# Usage: ./scripts/run_api.ps1

$env:PYTHONPATH = "$PWD/src;$PWD"
uvicorn app:app --reload --host 0.0.0.0 --port 8000
