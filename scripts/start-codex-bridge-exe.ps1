[CmdletBinding()]
param(
    [string]$Exe = "dist/codex-bridge.exe",
    [string]$Config = ".codex-bridge/server.json",
    [string]$HostOverride = "0.0.0.0",
    [int]$Port = 8765,
    [switch]$NativeUi,
    [switch]$Hidden,
    [switch]$RequireTokens,
    [switch]$NoAuth,
    [switch]$AllowLanNoToken,
    [switch]$AllowLanStaticUi
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ExePath = if ([System.IO.Path]::IsPathRooted($Exe)) {
    $Exe
} else {
    Join-Path $RepoRoot $Exe
}
$ConfigPath = if ([System.IO.Path]::IsPathRooted($Config)) {
    $Config
} else {
    Join-Path $RepoRoot $Config
}

if (-not (Test-Path -LiteralPath $ExePath)) {
    throw "Codex bridge exe not found: $ExePath. Run scripts\build-codex-bridge-exe.ps1 first."
}

if ($Hidden -and (-not $NativeUi)) {
    throw "-Hidden can only be used with -NativeUi."
}
if ($RequireTokens -and $NoAuth) {
    throw "-RequireTokens and -NoAuth cannot be used together."
}
if ($AllowLanNoToken -and (-not $NoAuth)) {
    throw "-AllowLanNoToken requires -NoAuth so the legacy no-token mode is explicit."
}

$ArgsList = @()
if (-not $NativeUi) {
    $ArgsList += "--headless"
}
if ($NativeUi -and $Hidden) {
    $ArgsList += "--hidden"
}
$ArgsList += @("--config", $ConfigPath, "--host", $HostOverride, "--port", $Port)
if ($NoAuth) {
    $ArgsList += "--no-auth"
}
if ((-not $NoAuth) -and ((-not $NativeUi) -or $RequireTokens)) {
    $ArgsList += "--require-tokens"
}
if ($AllowLanNoToken) {
    $ArgsList += "--allow-lan-no-token"
}
if ($AllowLanStaticUi) {
    $ArgsList += "--allow-lan-static-ui"
}

& $ExePath @ArgsList
exit $LASTEXITCODE
