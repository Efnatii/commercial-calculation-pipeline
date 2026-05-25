[CmdletBinding()]
param(
    [string]$OutputRoot = "artifacts",
    [string]$PackageName = "",
    [switch]$NoZip
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$DistExe = Join-Path $RepoRoot "dist\codex-bridge.exe"
if (-not (Test-Path -LiteralPath $DistExe)) {
    throw "Missing $DistExe. Run scripts\build-codex-bridge-exe.ps1 first."
}

function Get-RelativePackagePath {
    param(
        [string]$Root,
        [string]$Path
    )

    $RootFull = [System.IO.Path]::GetFullPath($Root)
    if (-not $RootFull.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
        $RootFull += [System.IO.Path]::DirectorySeparatorChar
    }
    $RootUri = [System.Uri]::new($RootFull)
    $PathUri = [System.Uri]::new([System.IO.Path]::GetFullPath($Path))
    return [System.Uri]::UnescapeDataString($RootUri.MakeRelativeUri($PathUri).ToString()).Replace("/", "\")
}

if (-not $PackageName) {
    $PackageName = "codex-bridge-release-{0}" -f (Get-Date -Format "yyyyMMdd-HHmmss")
}

$OutputRootPath = if ([System.IO.Path]::IsPathRooted($OutputRoot)) {
    $OutputRoot
} else {
    Join-Path $RepoRoot $OutputRoot
}
$PackageDir = Join-Path $OutputRootPath $PackageName

if (Test-Path -LiteralPath $PackageDir) {
    Remove-Item -LiteralPath $PackageDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $PackageDir | Out-Null

$Items = @(
    "dist\codex-bridge.exe",
    "configs\codex-bridge.example.json",
    "docs\codex-bridge.md",
    "docs\codex-bridge-acceptance.md",
    "docs\codex-bridge-architecture.md",
    "docs\codex-bridge-codex-cli-coverage.md",
    "docs\codex-bridge-openapi.json",
    "docs\codex-bridge-verification.md",
    "docs\index.html",
    "docs\.nojekyll",
    "docs\codex-ui",
    "scripts\start-codex-bridge-exe.ps1",
    "scripts\start-codex-bridge.ps1",
    "scripts\check-codex-bridge-coverage.ps1",
    "scripts\new-codex-bridge-cert.ps1",
    "scripts\open-codex-bridge-firewall.ps1",
    "scripts\install-codex-bridge-task.ps1",
    "scripts\uninstall-codex-bridge-task.ps1",
    "scripts\smoke-codex-bridge.ps1",
    "scripts\verify-codex-bridge.ps1",
    "tools\codex_bridge_cert.py"
)

foreach ($Item in $Items) {
    $Source = Join-Path $RepoRoot $Item
    if (-not (Test-Path -LiteralPath $Source)) {
        throw "Package input does not exist: $Source"
    }
    $Destination = Join-Path $PackageDir $Item
    $DestinationParent = Split-Path -Parent $Destination
    New-Item -ItemType Directory -Force -Path $DestinationParent | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
}

$Readme = @(
    "# Codex Bridge Release",
    "",
    "Start native tray/server mode on the strong machine:",
    "",
    "    .\dist\codex-bridge.exe",
    "",
    "Start the same executable headlessly:",
    "",
    "    .\scripts\start-codex-bridge-exe.ps1 -HostOverride 0.0.0.0 -Port 8765",
    "",
    "Headless mode requires a bridge token for LAN API callers by default.",
    "Use -RequireTokens when loopback callers must also provide a token:",
    "",
    "    .\scripts\start-codex-bridge-exe.ps1 -RequireTokens -HostOverride 0.0.0.0 -Port 8765",
    "",
    "Start native tray/server mode hidden at login or from a launcher:",
    "",
    "    .\scripts\start-codex-bridge-exe.ps1 -NativeUi -Hidden -HostOverride 0.0.0.0 -Port 8765",
    "",
    "The source-oriented scripts\start-codex-bridge.ps1 is included for command",
    "compatibility and delegates to the executable launcher inside this release",
    "package when tools\wrapper.py is absent.",
    "",
    "For LAN browser clients, open the GitHub Pages UI and set Bridge URL to",
    "the strong machine URL, for example http://192.168.1.10:8765.",
    "Standard https://*.github.io Pages origins are allowed by default.",
    "No Codex credential is required on weak clients, but LAN clients need",
    "a Codex Bridge bearer token. Issue user tokens from the local native UI",
    "on the strong machine. Direct bridge-hosted /ui access from LAN clients",
    "is disabled by default, and /health is loopback-only by default; enable",
    "security.allow_lan_static_ui or security.allow_lan_health only when that",
    "exposure is intentional.",
    "For HTTPS Pages, generate local TLS first:",
    "",
    "    .\scripts\new-codex-bridge-cert.ps1 -HostName 192.168.1.10 -HostName strong-pc",
    "",
    "Verify this package:",
    "",
    "    .\scripts\verify-codex-bridge.ps1",
    "",
    "Acceptance mapping is included at docs\codex-bridge-acceptance.md.",
    "",
    "This package-mode verification skips repository source tests because the",
    "handoff archive intentionally ships only the runtime executable, UI, docs,",
    "and operational scripts."
) -join [Environment]::NewLine
$ReadmePath = Join-Path $PackageDir "RELEASE_README.md"
$Readme | Set-Content -LiteralPath $ReadmePath -Encoding UTF8
$PrimaryReadmePath = Join-Path $PackageDir "README.md"
$Readme | Set-Content -LiteralPath $PrimaryReadmePath -Encoding UTF8

$Files = Get-ChildItem -LiteralPath $PackageDir -File -Recurse | Sort-Object FullName
$ManifestFiles = foreach ($File in $Files) {
    $RelativePath = (Get-RelativePackagePath -Root $PackageDir -Path $File.FullName).Replace("\", "/")
    [pscustomobject]@{
        path = $RelativePath
        size_bytes = $File.Length
        sha256 = (Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

$Manifest = [pscustomobject]@{
    name = $PackageName
    created_at = (Get-Date).ToString("o")
    repo_root = $RepoRoot
    manifest = [pscustomobject]@{
        includes_self = $false
        payload_file_count = @($ManifestFiles).Count
        note = "MANIFEST.json is generated after payload hashing and is intentionally excluded from its own hash list."
    }
    files = $ManifestFiles
}

$ManifestPath = Join-Path $PackageDir "MANIFEST.json"
$Manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ManifestPath -Encoding UTF8

$ZipPath = $null
if (-not $NoZip) {
    $ZipPath = Join-Path $OutputRootPath "$PackageName.zip"
    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }
    Compress-Archive -Path (Join-Path $PackageDir "*") -DestinationPath $ZipPath -CompressionLevel Optimal
}

[pscustomobject]@{
    ok = $true
    package_dir = $PackageDir
    zip_path = $ZipPath
    file_count = (Get-ChildItem -LiteralPath $PackageDir -File -Recurse).Count
    manifest_file_count = @($ManifestFiles).Count
    manifest = $ManifestPath
} | ConvertTo-Json -Compress
