[CmdletBinding()]
param(
    [string]$Config = "configs/rag-tool-check.toml",
    [string]$Python = "python",
    [switch]$Strict,
    [switch]$ReportOnly,
    [switch]$NoJsonReport
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Launcher = Join-Path $RepoRoot "tools\wrapper.py"
$ConfigPath = if ([System.IO.Path]::IsPathRooted($Config)) {
    $Config
} else {
    Join-Path $RepoRoot $Config
}

$ArgsList = @(
    $Launcher,
    "rag-anything",
    "check",
    "--",
    "--config", $ConfigPath,
    "--python", $Python
)

if ($Strict) {
    $ArgsList += "--strict"
}
if ($ReportOnly) {
    $ArgsList += "--report-only"
}
if ($NoJsonReport) {
    $ArgsList += "--no-json-report"
}

& $Python @ArgsList
exit $LASTEXITCODE
