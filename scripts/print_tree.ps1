# Print directory tree structure
# Usage: .\scripts\print_tree.ps1

Write-Host "Project Structure:"
Write-Host "==================`n"

Get-ChildItem -Recurse -Depth 3 -Exclude '.git','__pycache__','.pytest_cache','.ipynb_checkpoints','*.pyc' |
    Where-Object { $_.FullName -notlike '*\.git\*' -and $_.FullName -notlike '*\__pycache__\*' } |
    ForEach-Object {
        $indent = "  " * ($_.FullName.Split([IO.Path]::DirectorySeparatorChar).Count - $PWD.Path.Split([IO.Path]::DirectorySeparatorChar).Count - 1)
        if ($_.PSIsContainer) {
            Write-Host "$indent$($_.Name)/"
        } else {
            Write-Host "$indent$($_.Name)"
        }
    } | Sort-Object
