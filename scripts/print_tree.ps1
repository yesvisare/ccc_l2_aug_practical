# Print directory tree (depth 3)
Get-ChildItem -Recurse -Depth 3 | ForEach-Object {
    $indent = "  " * ($_.FullName.Split([IO.Path]::DirectorySeparatorChar).Count - $PWD.Path.Split([IO.Path]::DirectorySeparatorChar).Count - 1)
    "$indent$($_.Name)"
}
