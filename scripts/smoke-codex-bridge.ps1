[CmdletBinding()]
param(
    [string]$Python = "python",
    [int]$Port = 8810,
    [switch]$UseExe
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Config = Join-Path $RepoRoot ".codex-bridge\smoke-server.json"

function Stop-SmokeBridgeProcess {
    param(
        [System.Diagnostics.Process]$StartedProcess,
        [string]$ConfigPath,
        [int]$ListenPort
    )

    if ($StartedProcess -and -not $StartedProcess.HasExited) {
        Stop-Process -Id $StartedProcess.Id -Force -ErrorAction SilentlyContinue
    }

    Start-Sleep -Milliseconds 250
    $EscapedConfig = [System.Management.Automation.WildcardPattern]::Escape($ConfigPath)
    $Candidates = Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and
        $_.CommandLine -like "*$EscapedConfig*" -and
        $_.CommandLine -like "*--port $ListenPort*" -and
        ($_.CommandLine -like "*codex-bridge.exe*" -or $_.CommandLine -like "*codex-bridge-server.exe*" -or $_.CommandLine -like "*wrapper.py*")
    }
    foreach ($Candidate in $Candidates) {
        Stop-Process -Id $Candidate.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

$Launcher = Join-Path $RepoRoot "tools\wrapper.py"
$Exe = Join-Path $RepoRoot "dist\codex-bridge.exe"
if ((-not $UseExe) -and (-not (Test-Path -LiteralPath $Launcher)) -and (Test-Path -LiteralPath $Exe)) {
    $UseExe = $true
}

if ($UseExe) {
    if (-not (Test-Path -LiteralPath $Exe)) {
        throw "Missing exe: $Exe"
    }
    $Process = Start-Process -FilePath $Exe -ArgumentList @("--headless", "--config", $Config, "--host", "127.0.0.1", "--port", $Port, "--no-auth") -PassThru -WindowStyle Hidden
} else {
    if (-not (Test-Path -LiteralPath $Launcher)) {
        throw "Missing source launcher: $Launcher. Use -UseExe or run from a full repository checkout."
    }
    $Process = Start-Process -FilePath $Python -ArgumentList @($Launcher, "codex-bridge", "serve", "--", "--config", $Config, "--host", "127.0.0.1", "--port", $Port, "--no-auth") -PassThru -WindowStyle Hidden
}

try {
    $Base = "http://127.0.0.1:$Port"
    $Ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 400
        try {
            $Health = Invoke-RestMethod -Uri "$Base/health" -TimeoutSec 2
            if ($Health.ok -eq $true) {
                $Ready = $true
                break
            }
        } catch {}
    }
    if (-not $Ready) {
        throw "Bridge did not answer /health"
    }
    $Headers = @{}
    $Status = Invoke-RestMethod -Uri "$Base/api/status" -Headers $Headers -TimeoutSec 5
    $Capabilities = Invoke-RestMethod -Uri "$Base/api/capabilities" -Headers $Headers -TimeoutSec 5
    if (-not ($Capabilities.modes -contains "exec")) {
        throw "Capabilities missing exec mode"
    }

    $Body = @{ workspace_id = "main"; mode = "help"; topic = "codex"; timeout_seconds = 45 } | ConvertTo-Json
    $Job = Invoke-RestMethod -Uri "$Base/api/jobs" -Method Post -Headers $Headers -ContentType "application/json" -Body $Body -TimeoutSec 5
    $JobId = $Job.job.id
    $Done = $false
    for ($i = 0; $i -lt 90; $i++) {
        Start-Sleep -Milliseconds 500
        $JobStatus = Invoke-RestMethod -Uri "$Base/api/jobs/$JobId" -Headers $Headers -TimeoutSec 2
        if (@("completed", "failed", "cancelled") -contains $JobStatus.job.status) {
            $Done = $true
            break
        }
    }
    if (-not $Done) {
        throw "Help job did not finish"
    }

    [pscustomobject]@{
        ok = $true
        base_url = $Base
        codex_version = $Health.codex_version
        modes = $Capabilities.modes.Count
        help_job_status = $JobStatus.job.status
        workspace_count = $Status.workspaces.Count
    } | ConvertTo-Json -Compress
} finally {
    Stop-SmokeBridgeProcess -StartedProcess $Process -ConfigPath $Config -ListenPort $Port
}
