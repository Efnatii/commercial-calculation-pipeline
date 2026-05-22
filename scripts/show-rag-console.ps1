[CmdletBinding()]
param(
    [string]$Config = "configs/rag-tool-check.toml",
    [string]$Python = "python",
    [switch]$Strict,
    [switch]$Color,
    [switch]$Plain,
    [switch]$ReportOnly,
    [switch]$NoJsonReport
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Dashboard = Join-Path $RepoRoot "tools\rag_visual_console.py"
$ConfigPath = if ([System.IO.Path]::IsPathRooted($Config)) {
    $Config
} else {
    Join-Path $RepoRoot $Config
}

$ArgsList = @(
    $Dashboard,
    "--config", $ConfigPath,
    "--python", $Python
)

if ($Strict) {
    $ArgsList += "--strict"
}
if ($Color) {
    $ArgsList += "--color"
}
if ($Plain) {
    $ArgsList += "--plain"
}
if ($ReportOnly) {
    $ArgsList += "--report-only"
}
if ($NoJsonReport) {
    $ArgsList += "--no-json-report"
}

& $Python @ArgsList
exit $LASTEXITCODE
