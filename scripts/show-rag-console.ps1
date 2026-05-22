[CmdletBinding()]
param(
    [string]$Config = "configs/rag-tool-check.toml",
    [string]$Python = "python",
    [switch]$Strict,
    [switch]$Color,
    [switch]$Plain,
    [switch]$NoAnimations,
    [switch]$Details,
    [switch]$ReportOnly,
    [switch]$NoJsonReport,
    [switch]$NoPause
)

$ErrorActionPreference = "Stop"

$Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = $Utf8NoBom
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

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
    "visual",
    "--",
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
if ($NoAnimations) {
    $ArgsList += "--no-animations"
}
if ($Details) {
    $ArgsList += "--details"
}
if ($ReportOnly) {
    $ArgsList += "--report-only"
}
if ($NoJsonReport) {
    $ArgsList += "--no-json-report"
}

& $Python @ArgsList
$ExitCode = $LASTEXITCODE

if (-not $NoPause) {
    Write-Host ""
    $PauseMessage = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("0JPQvtGC0L7QstC+LiDQndCw0LbQvNC4IEVudGVyLCDRh9GC0L7QsdGLINC30LDQutGA0YvRgtGMINGN0YLQviDQvtC60L3Qvi4uLg=="))
    Write-Host $PauseMessage -ForegroundColor DarkGray
    [void][System.Console]::ReadLine()
}

exit $ExitCode
