$env:PYTHONPATH="$PWD/src;$PWD"
uvicorn app:app --reload
