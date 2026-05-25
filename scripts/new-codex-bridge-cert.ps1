[CmdletBinding()]
param(
    [string]$Config = ".codex-bridge/server.json",
    [string]$OutDir = ".codex-bridge/tls",
    [string[]]$HostName = @(),
    [int]$Days = 825,
    [string]$Python = "python",
    [string]$Venv = ".codex-bridge/cert-venv",
    [switch]$NoConfigUpdate
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPath = if ([System.IO.Path]::IsPathRooted($Venv)) { $Venv } else { Join-Path $RepoRoot $Venv }
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    & $Python -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$ConfigPath = if ([System.IO.Path]::IsPathRooted($Config)) { $Config } else { Join-Path $RepoRoot $Config }
$OutDirPath = if ([System.IO.Path]::IsPathRooted($OutDir)) { $OutDir } else { Join-Path $RepoRoot $OutDir }

& $VenvPython -m pip install --upgrade pip cryptography
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$ArgsList = @(
    (Join-Path $RepoRoot "tools\codex_bridge_cert.py"),
    "--config", $ConfigPath,
    "--out-dir", $OutDirPath,
    "--days", $Days
)

foreach ($Name in $HostName) {
    $ArgsList += @("--host", $Name)
}
if ($NoConfigUpdate) {
    $ArgsList += "--no-config-update"
}

& $VenvPython @ArgsList
exit $LASTEXITCODE
