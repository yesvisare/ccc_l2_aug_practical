$env:PYTHONPATH="$PWD/src;$PWD"
python3 -m pytest tests/ -q
