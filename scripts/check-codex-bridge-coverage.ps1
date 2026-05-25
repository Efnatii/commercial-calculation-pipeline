[CmdletBinding()]
param(
    [string]$Codex = "codex",
    [string]$Python = "python",
    [string]$CoverageDoc = "docs/codex-bridge-codex-cli-coverage.md",
    [switch]$Required
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$CoveragePath = if ([System.IO.Path]::IsPathRooted($CoverageDoc)) {
    $CoverageDoc
} else {
    Join-Path $Root $CoverageDoc
}

function Test-CommandAvailable {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-CodexHelpCommands {
    param([string[]]$HelpArgs = @())

    $Invocation = @()
    if ($HelpArgs) {
        $Invocation += $HelpArgs
    }
    $Invocation += "--help"
    $HelpOutput = & $Codex @Invocation 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "codex $($Invocation -join ' ') failed with exit code $LASTEXITCODE."
    }

    $Parsed = @()
    $InCommands = $false
    foreach ($Line in $HelpOutput) {
        if ($Line -match '^Commands:\s*$') {
            $InCommands = $true
            continue
        }
        if ($InCommands -and $Line -match '^\S') {
            break
        }
        if ($InCommands -and $Line -match '^\s{2}([a-z][a-z0-9-]*)\s+') {
            $Parsed += $Matches[1]
        }
    }
    return @($Parsed | Sort-Object -Unique)
}

if (-not (Test-CommandAvailable $Codex)) {
    $Message = "Codex CLI is not available; skipping live CLI coverage check."
    if ($Required) {
        throw $Message
    }
    Write-Host $Message
    return
}

if (-not (Test-Path -LiteralPath $CoveragePath)) {
    throw "Coverage document not found: $CoveragePath"
}

$Commands = Get-CodexHelpCommands
if (-not $Commands) {
    throw "Could not parse top-level commands from codex --help."
}

$Coverage = Get-Content -Raw -LiteralPath $CoveragePath
$MissingDocs = @()
foreach ($Command in $Commands) {
    if ($Coverage -notmatch [regex]::Escape("codex $Command")) {
        $MissingDocs += $Command
    }
}
if ($MissingDocs) {
    throw "Coverage document does not mention Codex command(s): $($MissingDocs -join ', ')"
}

$SourceDir = Join-Path $Root "tools\wrapper_modules\codex_bridge"
$MissingModes = @()
$NestedHelpPathsChecked = 0
if ((Test-Path -LiteralPath $SourceDir) -and (Test-CommandAvailable $Python)) {
    $ModeJson = & $Python -c @"
import json
import sys
from pathlib import Path
root = Path(r'$Root')
sys.path.insert(0, str(root / 'tools'))
from wrapper_modules.codex_bridge.core.codex import ALLOWED_MODES
print(json.dumps(sorted(ALLOWED_MODES)))
"@ 2>$null
    if ($LASTEXITCODE -eq 0 -and $ModeJson) {
        $Modes = $ModeJson | ConvertFrom-Json
        $RequiredModesByCommand = @{
            "exec" = @("exec", "exec-resume")
            "review" = @("review")
            "login" = @("login-status", "login-api-key", "login-access-token", "login-device-auth")
            "logout" = @("logout")
            "mcp" = @("mcp-list", "mcp-get", "mcp-add", "mcp-remove", "mcp-login", "mcp-logout")
            "plugin" = @("plugin-list", "plugin-add", "plugin-remove", "plugin-marketplace-list", "plugin-marketplace-add", "plugin-marketplace-remove", "plugin-marketplace-upgrade")
            "mcp-server" = @("mcp-server")
            "app-server" = @("app-server-start", "app-server-proxy", "app-server-generate-ts", "app-server-generate-json-schema", "app-daemon-version", "app-daemon-bootstrap", "app-daemon-start", "app-daemon-restart", "app-daemon-stop", "app-daemon-enable-remote", "app-daemon-disable-remote")
            "remote-control" = @("remote-start", "remote-stop")
            "app" = @("app-open")
            "completion" = @("completion")
            "update" = @("update")
            "doctor" = @("doctor")
            "sandbox" = @("sandbox-linux", "sandbox-macos", "sandbox-windows")
            "debug" = @("debug-models", "debug-app-server-send-message-v2", "debug-prompt-input")
            "apply" = @("apply")
            "resume" = @("resume")
            "fork" = @("fork")
            "cloud" = @("cloud-list", "cloud-status", "cloud-diff", "cloud-exec", "cloud-apply")
            "exec-server" = @("exec-server-start")
            "features" = @("features-list", "features-enable", "features-disable")
            "help" = @("help")
        }
        foreach ($Command in $Commands) {
            if (-not $RequiredModesByCommand.ContainsKey($Command)) {
                $MissingModes += "$Command (no bridge mode mapping)"
                continue
            }
            foreach ($Mode in $RequiredModesByCommand[$Command]) {
                if ($Mode -notin $Modes) {
                    $MissingModes += "$Command -> $Mode"
                }
            }
        }
        if ("raw" -notin $Modes) {
            $MissingModes += "raw fallback"
        }

        $RequiredModesBySubcommandHelp = @{
            "exec" = @{
                "resume" = @("exec-resume")
                "review" = @("review")
            }
            "login" = @{
                "status" = @("login-status")
            }
            "mcp" = @{
                "list" = @("mcp-list")
                "get" = @("mcp-get")
                "add" = @("mcp-add")
                "remove" = @("mcp-remove")
                "login" = @("mcp-login")
                "logout" = @("mcp-logout")
            }
            "plugin" = @{
                "add" = @("plugin-add")
                "list" = @("plugin-list")
                "marketplace" = @("plugin-marketplace-list", "plugin-marketplace-add", "plugin-marketplace-remove", "plugin-marketplace-upgrade")
                "remove" = @("plugin-remove")
            }
            "plugin marketplace" = @{
                "add" = @("plugin-marketplace-add")
                "list" = @("plugin-marketplace-list")
                "upgrade" = @("plugin-marketplace-upgrade")
                "remove" = @("plugin-marketplace-remove")
            }
            "features" = @{
                "list" = @("features-list")
                "enable" = @("features-enable")
                "disable" = @("features-disable")
            }
            "cloud" = @{
                "exec" = @("cloud-exec")
                "status" = @("cloud-status")
                "list" = @("cloud-list")
                "apply" = @("cloud-apply")
                "diff" = @("cloud-diff")
            }
            "sandbox" = @{
                "macos" = @("sandbox-macos")
                "linux" = @("sandbox-linux")
                "windows" = @("sandbox-windows")
            }
            "debug" = @{
                "models" = @("debug-models")
                "app-server" = @("debug-app-server-send-message-v2")
                "prompt-input" = @("debug-prompt-input")
            }
            "debug app-server" = @{
                "send-message-v2" = @("debug-app-server-send-message-v2")
            }
            "app-server" = @{
                "daemon" = @("app-daemon-version", "app-daemon-bootstrap", "app-daemon-start", "app-daemon-restart", "app-daemon-stop", "app-daemon-enable-remote", "app-daemon-disable-remote")
                "proxy" = @("app-server-proxy")
                "generate-ts" = @("app-server-generate-ts")
                "generate-json-schema" = @("app-server-generate-json-schema")
            }
            "app-server daemon" = @{
                "bootstrap" = @("app-daemon-bootstrap")
                "start" = @("app-daemon-start")
                "restart" = @("app-daemon-restart")
                "enable-remote-control" = @("app-daemon-enable-remote")
                "disable-remote-control" = @("app-daemon-disable-remote")
                "stop" = @("app-daemon-stop")
                "version" = @("app-daemon-version")
            }
            "remote-control" = @{
                "start" = @("remote-start")
                "stop" = @("remote-stop")
            }
        }

        foreach ($HelpPath in $RequiredModesBySubcommandHelp.Keys) {
            $NestedHelpPathsChecked += 1
            $Expected = $RequiredModesBySubcommandHelp[$HelpPath]
            $ActualSubcommands = Get-CodexHelpCommands -HelpArgs ($HelpPath -split " ")
            foreach ($Subcommand in $ActualSubcommands) {
                if ($Subcommand -eq "help") {
                    continue
                }
                if (-not $Expected.ContainsKey($Subcommand)) {
                    $MissingModes += "codex $HelpPath $Subcommand (no bridge mode mapping)"
                    continue
                }
                foreach ($Mode in $Expected[$Subcommand]) {
                    if ($Mode -notin $Modes) {
                        $MissingModes += "codex $HelpPath $Subcommand -> $Mode"
                    }
                }
            }
        }

        $LoginHelp = (& $Codex login --help 2>&1) -join "`n"
        $RequiredLoginOptions = @{
            "--with-api-key" = "login-api-key"
            "--with-access-token" = "login-access-token"
            "--device-auth" = "login-device-auth"
        }
        foreach ($Option in $RequiredLoginOptions.Keys) {
            if ($LoginHelp -match [regex]::Escape($Option) -and $RequiredLoginOptions[$Option] -notin $Modes) {
                $MissingModes += "codex login $Option -> $($RequiredLoginOptions[$Option])"
            }
        }
    }
}

if ($MissingModes) {
    throw "Bridge source is missing Codex mode coverage: $($MissingModes -join ', ')"
}

[pscustomobject]@{
    ok = $true
    codex_command_count = $Commands.Count
    codex_commands = $Commands
    nested_help_paths_checked = $NestedHelpPathsChecked
    source_modes_checked = [bool]((Test-Path -LiteralPath $SourceDir) -and (Test-CommandAvailable $Python) -and -not $MissingModes)
} | ConvertTo-Json -Compress
