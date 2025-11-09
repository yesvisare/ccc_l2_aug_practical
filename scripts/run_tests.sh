#!/bin/bash
# Run regression testing CI/CD tests
# Usage: ./scripts/run_tests.sh

export PYTHONPATH="$PWD"
echo "Running tests with pytest..."
pytest -v tests/

if [ $? -eq 0 ]; then
    echo -e "\n✓ All tests passed!"
else
    echo -e "\n✗ Some tests failed"
    exit 1
fi
