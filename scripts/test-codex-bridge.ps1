[CmdletBinding()]
param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepoRoot
try {
    & $Python -m unittest discover -s tests -p "test_codex_bridge*.py"
    exit $LASTEXITCODE
} finally {
    Pop-Location
}

