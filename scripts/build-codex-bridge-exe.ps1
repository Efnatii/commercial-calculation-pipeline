[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$Name = "codex-bridge",
    [string]$Dist = "dist",
    [string]$Venv = ".codex-bridge/build-venv",
    [switch]$Console,
    [switch]$NoStopRunning
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Launcher = Join-Path $RepoRoot "tools\wrapper.py"

if (-not $NoStopRunning) {
    $DistPath = if ([System.IO.Path]::IsPathRooted($Dist)) { $Dist } else { Join-Path $RepoRoot $Dist }
    $ExePath = Join-Path $DistPath "$Name.exe"
    $WebViewDir = Join-Path $RepoRoot ".codex-bridge\webview"
    $Running = Get-CimInstance Win32_Process | Where-Object {
        ($_.ExecutablePath -and [string]::Equals($_.ExecutablePath, $ExePath, [System.StringComparison]::OrdinalIgnoreCase)) -or
        ($_.ExecutablePath -like "*\msedgewebview2.exe" -and $_.CommandLine -like "*$WebViewDir*")
    }
    foreach ($Process in $Running) {
        Stop-Process -Id $Process.ProcessId -Force -ErrorAction SilentlyContinue
    }
    if ($Running) {
        Start-Sleep -Seconds 2
    }
}

$ArgsList = @(
    $Launcher,
    "codex-bridge",
    "build-exe",
    "--",
    "--python", $Python,
    "--name", $Name,
    "--dist", $Dist,
    "--venv", $Venv
)
if ($Console) {
    $ArgsList += "--console"
}

& $Python @ArgsList
exit $LASTEXITCODE
