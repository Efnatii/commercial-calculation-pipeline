[CmdletBinding()]
param(
    [string]$Python = "python",
    [int]$PortBase = 8820,
    [switch]$BuildExe,
    [switch]$Package,
    [switch]$Ui,
    [switch]$Native
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$ExePath = Join-Path $Root "dist\codex-bridge.exe"
$HasRepoSource = (Test-Path -LiteralPath (Join-Path $Root "tools\wrapper_modules\codex_bridge")) -and
    (Test-Path -LiteralPath (Join-Path $Root "tests\test_codex_bridge_core.py"))

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Body
    )

    Write-Host "== $Name =="
    & $Body
}

function Test-CommandAvailable {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-TcpPortAvailable {
    param([int]$Port)

    $Listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return -not [bool]$Listeners
}

function Assert-RequiredTcpPortsAvailable {
    param([int[]]$Ports)

    $Busy = @()
    foreach ($Port in ($Ports | Sort-Object -Unique)) {
        if (-not (Test-TcpPortAvailable -Port $Port)) {
            $Owners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
                Select-Object -ExpandProperty OwningProcess -Unique |
                ForEach-Object {
                    $Process = Get-CimInstance Win32_Process -Filter "ProcessId=$_" -ErrorAction SilentlyContinue
                    if ($Process) {
                        "$($Process.ProcessId): $($Process.ExecutablePath)"
                    } else {
                        "${_}: unknown process"
                    }
                }
            $Busy += "port $Port is already listening ($($Owners -join '; '))"
        }
    }
    if ($Busy) {
        throw "Codex Bridge verification needs free TCP ports. Choose another -PortBase. Busy ports: $($Busy -join ', ')"
    }
}

function Assert-UnderPath {
    param(
        [string]$Path,
        [string]$Parent
    )

    $FullPath = [System.IO.Path]::GetFullPath($Path)
    $FullParent = [System.IO.Path]::GetFullPath($Parent)
    if (-not $FullParent.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
        $FullParent += [System.IO.Path]::DirectorySeparatorChar
    }
    if (-not (($FullPath + [System.IO.Path]::DirectorySeparatorChar).StartsWith($FullParent, [System.StringComparison]::OrdinalIgnoreCase))) {
        throw "Refusing to operate outside expected root: $FullPath"
    }
}

function Stop-CodexBridgeProcess {
    $WebViewDir = Join-Path $Root ".codex-bridge\webview"
    $Processes = Get-CimInstance Win32_Process | Where-Object {
        ($_.ExecutablePath -and [string]::Equals($_.ExecutablePath, $ExePath, [System.StringComparison]::OrdinalIgnoreCase)) -or
        ($_.ExecutablePath -like "*\msedgewebview2.exe" -and $_.CommandLine -like "*$WebViewDir*")
    }
    foreach ($Process in $Processes) {
        Stop-Process -Id $Process.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 500
}

function Wait-BridgeHealth {
    param(
        [int]$Port,
        [System.Diagnostics.Process]$Process
    )

    for ($i = 0; $i -lt 45; $i++) {
        Start-Sleep -Milliseconds 400
        if ($Process -and $Process.HasExited) {
            throw "Codex Bridge exited early with code $($Process.ExitCode)."
        }
        try {
            $Health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2
            if ($Health.ok) {
                return $Health
            }
        } catch {}
    }
    throw "Codex Bridge did not answer /health on port $Port."
}

function Get-VisibleWindowTitles {
    if (-not ("CodexBridgeWindowEnum" -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class CodexBridgeWindowEnum {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
  public static string[] Titles() {
    var titles = new List<string>();
    EnumWindows((hWnd, lParam) => {
      if (IsWindowVisible(hWnd)) {
        var sb = new StringBuilder(512);
        GetWindowText(hWnd, sb, sb.Capacity);
        var title = sb.ToString();
        if (!string.IsNullOrWhiteSpace(title)) titles.Add(title);
      }
      return true;
    }, IntPtr.Zero);
    return titles.ToArray();
  }
}
'@
    }
    return [CodexBridgeWindowEnum]::Titles()
}

Push-Location $Root
try {
    $RequiredPorts = @(($PortBase + 1), ($PortBase + 6), ($PortBase + 8))
    if ($HasRepoSource) {
        $RequiredPorts += $PortBase
    }
    if ((Test-Path -LiteralPath "scripts\new-codex-bridge-cert.ps1") -and (Test-Path -LiteralPath "tools\codex_bridge_cert.py")) {
        $RequiredPorts += ($PortBase + 9)
    }
    if ($Ui) {
        $RequiredPorts += ($PortBase + 2)
    }
    if ($Native) {
        $RequiredPorts += @(($PortBase + 3), ($PortBase + 4), ($PortBase + 7))
    }
    if ((-not $HasRepoSource) -and (Test-Path -LiteralPath "scripts\start-codex-bridge.ps1")) {
        $RequiredPorts += ($PortBase + 10)
    }
    Invoke-Step "TCP port availability" {
        Assert-RequiredTcpPortsAvailable -Ports $RequiredPorts
    }

    if ($HasRepoSource) {
        Invoke-Step "Unit tests" {
            & $Python -m unittest discover -s tests -p "test_codex_bridge*.py"
            if ($LASTEXITCODE -ne 0) { throw "Unit tests failed." }
        }

        Invoke-Step "Python compile" {
            & $Python -m compileall -q tools\wrapper_modules\codex_bridge tools\codex_bridge_server.py tools\codex_bridge_app.py tools\codex_bridge_cert.py
            if ($LASTEXITCODE -ne 0) { throw "Python compile failed." }
        }

        if (Test-CommandAvailable "node") {
            Invoke-Step "UI JavaScript syntax" {
                node --check docs\codex-ui\app.js
                if ($LASTEXITCODE -ne 0) { throw "UI JavaScript check failed." }
            }
        } else {
            Write-Host "== UI JavaScript syntax skipped: node is not available =="
        }
        if (Test-CommandAvailable "npx") {
            Invoke-Step "UI and workflow formatting" {
                npx --yes prettier --check ".github/workflows/*.yml" "docs/**/*.html" "docs/**/*.css" "docs/**/*.js"
                if ($LASTEXITCODE -ne 0) { throw "Prettier check failed." }
            }
        } else {
            Write-Host "== UI and workflow formatting skipped: npx is not available =="
        }
    } else {
        Write-Host "== Source checks skipped: release package has no tools/tests source tree =="
        if ($BuildExe -or $Package) {
            throw "-BuildExe and -Package require a full repository checkout."
        }
    }

    if (Test-Path -LiteralPath "docs\codex-bridge-openapi.json") {
        Invoke-Step "OpenAPI JSON" {
            Get-Content -Raw docs\codex-bridge-openapi.json | ConvertFrom-Json | Out-Null
        }
    }

    if (Test-Path -LiteralPath "MANIFEST.json") {
        Invoke-Step "Package manifest" {
            $Manifest = Get-Content -Raw -LiteralPath "MANIFEST.json" | ConvertFrom-Json
            $Entries = @($Manifest.files)
            if (-not $Entries) {
                throw "Package manifest has no file entries."
            }
            $Failures = @()
            foreach ($Entry in $Entries) {
                $Relative = ([string]$Entry.path).Replace("/", "\")
                $FilePath = Join-Path $Root $Relative
                if (-not (Test-Path -LiteralPath $FilePath)) {
                    $Failures += "Missing file listed in manifest: $Relative"
                    continue
                }
                $Item = Get-Item -LiteralPath $FilePath
                if ($Item.Length -ne [int64]$Entry.size_bytes) {
                    $Failures += "Size mismatch for $Relative"
                    continue
                }
                $Hash = (Get-FileHash -LiteralPath $FilePath -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($Hash -ne [string]$Entry.sha256) {
                    $Failures += "SHA-256 mismatch for $Relative"
                }
            }
            if ("docs/codex-bridge-acceptance.md" -notin @($Entries | ForEach-Object { [string]$_.path })) {
                $Failures += "Acceptance map is not listed in package manifest."
            }
            $ActualFileCount = @(Get-ChildItem -LiteralPath $Root -File -Recurse).Count
            if ($ActualFileCount -ne ($Entries.Count + 1)) {
                $Failures += "Package has $ActualFileCount files but manifest lists $($Entries.Count) payload files plus MANIFEST.json."
            }
            if ($Manifest.manifest.includes_self -ne $false) {
                $Failures += "Manifest metadata should state includes_self=false."
            }
            $ReadmePath = Join-Path $Root "README.md"
            if (Test-Path -LiteralPath $ReadmePath) {
                $ReadmeHead = Get-Content -LiteralPath $ReadmePath -TotalCount 1
                if ($ReadmeHead -ne "# Codex Bridge Release") {
                    $Failures += "Release package README.md should start with '# Codex Bridge Release'."
                }
                $ReadmeBody = Get-Content -LiteralPath $ReadmePath -Raw
                if ($ReadmeBody -match "RAG-Anything Wrapper") {
                    $Failures += "Release package README.md should not contain the source repository RAG section."
                }
            } else {
                $Failures += "Release package README.md is missing."
            }
            if ($Failures) {
                $Failures | ForEach-Object { Write-Error $_ }
                throw "Package manifest verification failed."
            }
        }
    }

    if (Test-Path -LiteralPath "scripts\check-codex-bridge-coverage.ps1") {
        Invoke-Step "Codex CLI coverage" {
            .\scripts\check-codex-bridge-coverage.ps1 -Python $Python
        }
    }

    if ((Test-Path -LiteralPath "scripts\new-codex-bridge-cert.ps1") -and (Test-Path -LiteralPath "tools\codex_bridge_cert.py")) {
        Invoke-Step "Certificate helper and TLS smoke" {
            Stop-CodexBridgeProcess
            $CertRoot = Join-Path $Root ".codex-bridge\verify-cert"
            $CertConfig = Join-Path $CertRoot "server.json"
            $CertOut = Join-Path $CertRoot "tls"
            $CertVenv = Join-Path $CertRoot "venv"
            Assert-UnderPath -Path $CertRoot -Parent (Join-Path $Root ".codex-bridge")
            if (Test-Path -LiteralPath $CertRoot) {
                Remove-Item -LiteralPath $CertRoot -Recurse -Force
            }
            New-Item -ItemType Directory -Force -Path $CertRoot | Out-Null
            @{
                server = @{
                    port = $PortBase + 9
                }
                runtime = @{
                    state_dir = ".codex-bridge/verify-cert/state"
                }
            } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $CertConfig -Encoding UTF8

            .\scripts\new-codex-bridge-cert.ps1 -Config $CertConfig -OutDir $CertOut -Venv $CertVenv -HostName 127.0.0.1 -Days 1 -Python $Python | Out-Null
            $GeneratedConfig = Get-Content -Raw -LiteralPath $CertConfig | ConvertFrom-Json
            if (-not $GeneratedConfig.server.tls.enabled) {
                throw "Certificate helper did not enable server.tls."
            }
            foreach ($Pem in @($GeneratedConfig.server.tls.cert_file, $GeneratedConfig.server.tls.key_file)) {
                if (-not (Test-Path -LiteralPath $Pem)) {
                    throw "Certificate helper did not create PEM file: $Pem"
                }
            }

            if (-not (Test-CommandAvailable "curl.exe")) {
                throw "curl.exe is required for TLS smoke with a self-signed certificate."
            }
            $Process = Start-Process -FilePath $ExePath -ArgumentList @("--headless", "--config", $CertConfig, "--host", "127.0.0.1", "--port", ($PortBase + 9), "--no-auth") -PassThru -WindowStyle Hidden
            try {
                $TlsHealth = $null
                for ($i = 0; $i -lt 45; $i++) {
                    Start-Sleep -Milliseconds 400
                    if ($Process.HasExited) {
                        throw "TLS Codex Bridge exited early with code $($Process.ExitCode)."
                    }
                    try {
                        $TlsHealthRaw = & curl.exe --silent --show-error --fail --insecure --max-time 2 "https://127.0.0.1:$($PortBase + 9)/health" 2>$null
                        if ($LASTEXITCODE -eq 0 -and $TlsHealthRaw) {
                            $TlsHealth = $TlsHealthRaw | ConvertFrom-Json
                            if ($TlsHealth.ok) {
                                break
                            }
                        }
                    } catch {}
                }
                if (-not $TlsHealth -or -not $TlsHealth.ok) {
                    throw "TLS Codex Bridge did not answer /health."
                }
            } finally {
                Stop-CodexBridgeProcess
                if ($Process -and -not $Process.HasExited) {
                    Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
                }
            }
        }
    }

    Invoke-Step "PowerShell parser" {
        $Failures = @()
        Get-ChildItem -Path scripts -Filter *.ps1 | ForEach-Object {
            $Tokens = $null
            $Errors = $null
            [System.Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$Tokens, [ref]$Errors) | Out-Null
            if ($Errors.Count -gt 0) {
                $Failures += [pscustomobject]@{
                    path = $_.FullName
                    errors = ($Errors | ForEach-Object Message) -join "; "
                }
            }
        }
        if ($Failures.Count -gt 0) {
            $Failures | Format-List | Out-String | Write-Error
            throw "PowerShell parser found errors."
        }
    }

    Invoke-Step "Scheduled task dry run" {
        $TaskPreview = .\scripts\install-codex-bridge-task.ps1 -NativeUi -Hidden -DryRun | ConvertFrom-Json
        if (-not $TaskPreview.ok) {
            throw "Scheduled task dry run did not return ok=true."
        }
        if ($TaskPreview.argument -notmatch "--hidden") {
            throw "Scheduled task dry run does not include --hidden."
        }
        if ($TaskPreview.argument -match "--headless") {
            throw "Native scheduled task dry run unexpectedly includes --headless."
        }
        $LockedPreview = .\scripts\install-codex-bridge-task.ps1 -RequireTokens -DryRun | ConvertFrom-Json
        if ($LockedPreview.argument -notmatch "--headless") {
            throw "Headless scheduled task dry run does not include --headless."
        }
        if ($LockedPreview.argument -notmatch "--require-tokens") {
            throw "Headless scheduled task dry run does not include --require-tokens."
        }
        if ($LockedPreview.argument -match "--no-auth") {
            throw "Locked-down scheduled task dry run unexpectedly includes --no-auth."
        }
    }

    if ($BuildExe) {
        Invoke-Step "Build executable" {
            .\scripts\build-codex-bridge-exe.ps1
        }
    }

    if ($HasRepoSource) {
        Invoke-Step "Source smoke" {
            .\scripts\smoke-codex-bridge.ps1 -Python $Python -Port $PortBase
        }
    }

    if (-not (Test-Path -LiteralPath $ExePath)) {
        throw "Missing executable: $ExePath"
    }

    Invoke-Step "Executable smoke" {
        .\scripts\smoke-codex-bridge.ps1 -UseExe -Port ($PortBase + 1)
    }

    Invoke-Step "Start script headless smoke" {
        Stop-CodexBridgeProcess
        $Config = Join-Path $Root ".codex-bridge\verify-start-script-headless.json"
        $Launcher = Start-Process -FilePath "powershell.exe" -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            (Join-Path $Root "scripts\start-codex-bridge-exe.ps1"),
            "-Config",
            $Config,
            "-HostOverride",
            "127.0.0.1",
            "-Port",
            ($PortBase + 6)
        ) -PassThru -WindowStyle Hidden
        try {
            Wait-BridgeHealth -Port ($PortBase + 6) -Process $null | Out-Null
        } finally {
            Stop-CodexBridgeProcess
            if ($Launcher -and -not $Launcher.HasExited) {
                Stop-Process -Id $Launcher.Id -Force -ErrorAction SilentlyContinue
            }
        }
    }

    Invoke-Step "Start script headless token-auth smoke" {
        Stop-CodexBridgeProcess
        $StateDir = Join-Path $Root ".codex-bridge\verify-token-auth-state"
        Assert-UnderPath -Path $StateDir -Parent (Join-Path $Root ".codex-bridge")
        if (Test-Path -LiteralPath $StateDir) {
            Remove-Item -LiteralPath $StateDir -Recurse -Force
        }
        $Config = Join-Path $Root ".codex-bridge\verify-start-script-headless-tokens.json"
        @{
            runtime = @{
                state_dir = ".codex-bridge/verify-token-auth-state"
            }
        } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $Config -Encoding UTF8
        $Port = $PortBase + 8
        $Launcher = Start-Process -FilePath "powershell.exe" -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            (Join-Path $Root "scripts\start-codex-bridge-exe.ps1"),
            "-Config",
            $Config,
            "-HostOverride",
            "127.0.0.1",
            "-Port",
            $Port,
            "-RequireTokens"
        ) -PassThru -WindowStyle Hidden
        try {
            Wait-BridgeHealth -Port $Port -Process $null | Out-Null
            try {
                Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/status" -TimeoutSec 2 | Out-Null
                throw "Token-auth headless server allowed /api/status without a token."
            } catch {
                if ($_.Exception.Response.StatusCode.value__ -ne 403) {
                    throw
                }
            }
            $BootstrapTokenPath = Join-Path $StateDir "bootstrap-admin-token.txt"
            if (-not (Test-Path -LiteralPath $BootstrapTokenPath)) {
                throw "Token-auth headless server did not create a bootstrap admin token."
            }
            $Token = (Get-Content -LiteralPath $BootstrapTokenPath -Raw).Trim()
            $Status = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/status" -Headers @{ Authorization = "Bearer $Token" } -TimeoutSec 5
            if (-not $Status.ok -or -not $Status.config.security.require_api_tokens) {
                throw "Token-auth headless server did not require tokens after authenticated status check."
            }
        } finally {
            Stop-CodexBridgeProcess
            if ($Launcher -and -not $Launcher.HasExited) {
                Stop-Process -Id $Launcher.Id -Force -ErrorAction SilentlyContinue
            }
        }
    }

    if ((-not $HasRepoSource) -and (Test-Path -LiteralPath "scripts\start-codex-bridge.ps1")) {
        Invoke-Step "Release compatibility start script smoke" {
            Stop-CodexBridgeProcess
            $Config = Join-Path $Root ".codex-bridge\verify-release-compat.json"
            $Launcher = Start-Process -FilePath "powershell.exe" -ArgumentList @(
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                (Join-Path $Root "scripts\start-codex-bridge.ps1"),
                "-Config",
                $Config,
                "-HostOverride",
                "127.0.0.1",
                "-Port",
                ($PortBase + 10)
            ) -PassThru -WindowStyle Hidden
            try {
                Wait-BridgeHealth -Port ($PortBase + 10) -Process $null | Out-Null
            } finally {
                Stop-CodexBridgeProcess
                if ($Launcher -and -not $Launcher.HasExited) {
                    Stop-Process -Id $Launcher.Id -Force -ErrorAction SilentlyContinue
                }
            }
        }
    }

    if ($Ui) {
        if (-not (Test-CommandAvailable "npx")) {
            throw "npx is required for -Ui browser screenshots."
        }
        Invoke-Step "Browser UI smoke" {
            $Config = Join-Path $Root ".codex-bridge\verify-ui-server.json"
            $Output = Join-Path $Root ".codex-bridge\playwright"
            New-Item -ItemType Directory -Force -Path $Output | Out-Null
            $Process = Start-Process -FilePath $ExePath -ArgumentList @("--headless", "--config", $Config, "--host", "127.0.0.1", "--port", ($PortBase + 2), "--no-auth") -PassThru -WindowStyle Hidden
            try {
                $Base = "http://127.0.0.1:$($PortBase + 2)"
                Wait-BridgeHealth -Port ($PortBase + 2) -Process $Process | Out-Null
                npx --yes playwright screenshot --browser chromium --channel msedge --viewport-size "1440,960" --wait-for-selector ".status-pill.is-online" --wait-for-timeout 1000 "$Base/ui" (Join-Path $Output "codex-ui-desktop.png")
                npx --yes playwright screenshot --browser chromium --channel msedge --viewport-size "390,844" --wait-for-selector ".status-pill.is-online" --wait-for-timeout 1000 "$Base/ui" (Join-Path $Output "codex-ui-mobile.png")
            } finally {
                if ($Process -and -not $Process.HasExited) {
                    Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
                }
            }
        }
    }

    if ($Native) {
        Invoke-Step "Native WebView hidden smoke" {
            Stop-CodexBridgeProcess
            $Config = Join-Path $Root ".codex-bridge\verify-native-hidden.json"
            $Process = Start-Process -FilePath $ExePath -ArgumentList @("--hidden", "--config", $Config, "--host", "127.0.0.1", "--port", ($PortBase + 3)) -PassThru -WindowStyle Hidden
            try {
                Wait-BridgeHealth -Port ($PortBase + 3) -Process $Process | Out-Null
            } finally {
                Stop-CodexBridgeProcess
            }
        }

        Invoke-Step "Native WebView visible smoke" {
            Stop-CodexBridgeProcess
            $Config = Join-Path $Root ".codex-bridge\verify-native-visible.json"
            $Process = Start-Process -FilePath $ExePath -ArgumentList @("--config", $Config, "--host", "127.0.0.1", "--port", ($PortBase + 4)) -PassThru
            try {
                Wait-BridgeHealth -Port ($PortBase + 4) -Process $Process | Out-Null
                Start-Sleep -Seconds 2
                $Titles = Get-VisibleWindowTitles | Where-Object { $_ -like "*Codex Bridge*" }
                if (-not $Titles) {
                    throw "Visible Codex Bridge WebView2 window was not found."
                }
            } finally {
                Stop-CodexBridgeProcess
            }
        }

        Invoke-Step "Start script native UI smoke" {
            Stop-CodexBridgeProcess
            $Config = Join-Path $Root ".codex-bridge\verify-start-script-native.json"
            $Launcher = Start-Process -FilePath "powershell.exe" -ArgumentList @(
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                (Join-Path $Root "scripts\start-codex-bridge-exe.ps1"),
                "-NativeUi",
                "-Hidden",
                "-Config",
                $Config,
                "-HostOverride",
                "127.0.0.1",
                "-Port",
                ($PortBase + 7)
            ) -PassThru -WindowStyle Hidden
            try {
                $Health = $null
                for ($i = 0; $i -lt 45; $i++) {
                    Start-Sleep -Milliseconds 400
                    if ($Launcher.HasExited -and $Launcher.ExitCode -ne 0) {
                        throw "Native start script exited with code $($Launcher.ExitCode)."
                    }
                    try {
                        $Health = Invoke-RestMethod -Uri "http://127.0.0.1:$($PortBase + 7)/health" -TimeoutSec 2
                        if ($Health.ok) {
                            break
                        }
                    } catch {}
                }
                if (-not $Health -or -not $Health.ok) {
                    throw "Native start script did not answer /health."
                }
                $Bridge = Get-CimInstance Win32_Process | Where-Object {
                    $_.ExecutablePath -and [string]::Equals($_.ExecutablePath, $ExePath, [System.StringComparison]::OrdinalIgnoreCase)
                } | Select-Object -First 1
                if (-not $Bridge) {
                    throw "Native start script did not leave codex-bridge.exe running."
                }
            } finally {
                Stop-CodexBridgeProcess
                if ($Launcher -and -not $Launcher.HasExited) {
                    Stop-Process -Id $Launcher.Id -Force -ErrorAction SilentlyContinue
                }
            }
        }
    }

    if ($Package) {
        Invoke-Step "Package and extracted verify" {
            .\scripts\package-codex-bridge-release.ps1 -PackageName codex-bridge-release-verify
            $VerifyDir = Join-Path $Root ".codex-bridge\verify-package"
            Assert-UnderPath -Path $VerifyDir -Parent (Join-Path $Root ".codex-bridge")
            if (Test-Path -LiteralPath $VerifyDir) {
                Remove-Item -LiteralPath $VerifyDir -Recurse -Force
            }
            New-Item -ItemType Directory -Force -Path $VerifyDir | Out-Null
            Expand-Archive -LiteralPath (Join-Path $Root "artifacts\codex-bridge-release-verify.zip") -DestinationPath $VerifyDir -Force
            Push-Location $VerifyDir
            try {
                .\scripts\verify-codex-bridge.ps1 -PortBase ($PortBase + 5)
            } finally {
                Pop-Location
            }
        }
    }

    Invoke-Step "Process cleanup check" {
        Stop-CodexBridgeProcess
        $Remaining = Get-CimInstance Win32_Process | Where-Object {
            $_.ExecutablePath -and [string]::Equals($_.ExecutablePath, $ExePath, [System.StringComparison]::OrdinalIgnoreCase)
        }
        if ($Remaining) {
            throw "Codex Bridge process still running after cleanup."
        }
    }

    [pscustomobject]@{
        ok = $true
        source_checks = [bool]$HasRepoSource
        build_exe = [bool]$BuildExe
        package = [bool]$Package
        ui = [bool]$Ui
        native = [bool]$Native
    } | ConvertTo-Json -Compress
} finally {
    Pop-Location
}
