[CmdletBinding()]
param(
    [string]$Config = ".codex-bridge/server.json",
    [string]$Python = "python",
    [string]$HostOverride = "",
    [int]$Port = 0,
    [switch]$Init,
    [switch]$RequireTokens,
    [switch]$NoAuth,
    [switch]$NoLoopbackBypass,
    [switch]$AllowLanNoToken,
    [switch]$AllowLanStaticUi
)

$ErrorActionPreference = "Stop"

if ($RequireTokens -and $NoAuth) {
    throw "-RequireTokens and -NoAuth cannot be used together."
}
if ($AllowLanNoToken -and (-not $NoAuth)) {
    throw "-AllowLanNoToken requires -NoAuth so the legacy no-token mode is explicit."
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Launcher = Join-Path $RepoRoot "tools\wrapper.py"
$ExeLauncher = Join-Path $RepoRoot "scripts\start-codex-bridge-exe.ps1"
$ConfigPath = if ([System.IO.Path]::IsPathRooted($Config)) {
    $Config
} else {
    Join-Path $RepoRoot $Config
}

if (-not (Test-Path -LiteralPath $Launcher)) {
    if (Test-Path -LiteralPath $ExeLauncher) {
        if ($NoLoopbackBypass -and (-not $RequireTokens)) {
            throw "-NoLoopbackBypass requires source checkout mode or -RequireTokens in release package mode."
        }
        $FallbackArgs = @{
            Config = $ConfigPath
        }
        if ($HostOverride) {
            $FallbackArgs.HostOverride = $HostOverride
        }
        if ($Port -gt 0) {
            $FallbackArgs.Port = $Port
        }
        if ($RequireTokens) {
            $FallbackArgs.RequireTokens = $true
        }
        if ($NoAuth) {
            $FallbackArgs.NoAuth = $true
        }
        if ($AllowLanNoToken) {
            $FallbackArgs.AllowLanNoToken = $true
        }
        if ($AllowLanStaticUi) {
            $FallbackArgs.AllowLanStaticUi = $true
        }
        & $ExeLauncher @FallbackArgs
        exit $LASTEXITCODE
    }
    throw "Source launcher not found: $Launcher. Use scripts\start-codex-bridge-exe.ps1 from a release package."
}

if ($Init -or -not (Test-Path -LiteralPath $ConfigPath)) {
    & $Python $Launcher codex-bridge init -- --config $ConfigPath
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$ArgsList = @(
    $Launcher,
    "codex-bridge",
    "serve",
    "--",
    "--config", $ConfigPath
)

if ($HostOverride) {
    $ArgsList += @("--host", $HostOverride)
}
if ($Port -gt 0) {
    $ArgsList += @("--port", $Port)
}
if ($RequireTokens) {
    $ArgsList += "--require-tokens"
}
if ($NoAuth) {
    $ArgsList += "--no-auth"
}
if ($AllowLanNoToken) {
    $ArgsList += "--allow-lan-no-token"
}
if ($AllowLanStaticUi) {
    $ArgsList += "--allow-lan-static-ui"
}
if ($NoLoopbackBypass) {
    $ArgsList += "--no-loopback-bypass"
}

& $Python @ArgsList
exit $LASTEXITCODE
