[CmdletBinding()]
param(
    [string]$TaskName = "Codex Bridge LAN",
    [string]$Exe = "dist/codex-bridge.exe",
    [string]$Config = ".codex-bridge/server.json",
    [string]$HostOverride = "0.0.0.0",
    [int]$Port = 8765,
    [switch]$NativeUi,
    [switch]$Hidden,
    [switch]$RequireTokens,
    [switch]$NoAuth,
    [switch]$AllowLanNoToken,
    [switch]$AllowLanStaticUi,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ExePath = if ([System.IO.Path]::IsPathRooted($Exe)) { $Exe } else { Join-Path $RepoRoot $Exe }
$ConfigPath = if ([System.IO.Path]::IsPathRooted($Config)) { $Config } else { Join-Path $RepoRoot $Config }

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
if ($NativeUi) {
    if ($Hidden) {
        $ArgsList += "--hidden"
    }
} else {
    $ArgsList += "--headless"
}
$ArgsList += @("--config", "`"$ConfigPath`"", "--host", "`"$HostOverride`"", "--port", $Port)
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
$Argument = ($ArgsList -join " ").Trim()

if ($DryRun) {
    [pscustomobject]@{
        ok = $true
        dry_run = $true
        task_name = $TaskName
        execute = $ExePath
        argument = $Argument
        working_directory = $RepoRoot
        native_ui = [bool]$NativeUi
        hidden = [bool]$Hidden
        require_tokens = (-not [bool]$NoAuth)
        no_auth = [bool]$NoAuth
        allow_lan_no_token = [bool]$AllowLanNoToken
        allow_lan_static_ui = [bool]$AllowLanStaticUi
    } | ConvertTo-Json -Compress
    return
}

$Action = New-ScheduledTaskAction -Execute $ExePath -Argument $Argument -WorkingDirectory $RepoRoot
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Days 365)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Runs Codex Bridge for LAN browser clients." `
    -Force | Out-Null

Write-Host "Scheduled task installed: $TaskName"
