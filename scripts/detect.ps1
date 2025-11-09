# Detect changes in document corpus
# Usage: .\scripts\detect.ps1 [documents_dir]
# Example: .\scripts\detect.ps1 example_documents

param(
    [string]$DocumentsDir = "example_documents"
)

$env:PYTHONPATH = $PWD
Write-Host "Detecting changes in: $DocumentsDir"
python -m m5_1_incremental_indexing.core detect $DocumentsDir
