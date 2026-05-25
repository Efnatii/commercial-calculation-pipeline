[CmdletBinding()]
param()

$Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = $Utf8NoBom
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom

function Set-DefaultEnv {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Value
    )

    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($Name, "Process"))) {
        [Environment]::SetEnvironmentVariable($Name, $Value, "Process")
    }
}

function Add-PathEntry {
    param(
        [string]$Path,
        [switch]$Append
    )

    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path)) {
        return
    }

    $Resolved = (Resolve-Path -LiteralPath $Path).Path
    $Parts = $env:PATH -split [System.IO.Path]::PathSeparator
    if (-not ($Parts | Where-Object { $_ -ieq $Resolved })) {
        $Separator = [System.IO.Path]::PathSeparator
        $env:PATH = if ($Append) {
            "$env:PATH$Separator$Resolved"
        } else {
            "$Resolved$Separator$env:PATH"
        }
    }
}

function Add-PythonPathEntry {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path)) {
        return
    }

    $Resolved = (Resolve-Path -LiteralPath $Path).Path
    $Parts = @()
    if (-not [string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
        $Parts = $env:PYTHONPATH -split [System.IO.Path]::PathSeparator
    }
    if (-not ($Parts | Where-Object { $_ -ieq $Resolved })) {
        $env:PYTHONPATH = if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
            $Resolved
        } else {
            "$Resolved$([System.IO.Path]::PathSeparator)$env:PYTHONPATH"
        }
    }
}

function Resolve-WorkbenchRoot {
    $Candidates = @(
        $env:WORKBENCH_ROOT,
        [Environment]::GetEnvironmentVariable("WORKBENCH_ROOT", "User"),
        [Environment]::GetEnvironmentVariable("WORKBENCH_ROOT", "Machine"),
        "C:\_wb"
    )
    foreach ($Candidate in $Candidates) {
        if (-not [string]::IsNullOrWhiteSpace($Candidate) -and
            (Test-Path -LiteralPath (Join-Path $Candidate "00_ROUTING\AI_ROUTING.md"))) {
            return (Resolve-Path -LiteralPath $Candidate).Path
        }
    }
    return $null
}

function Initialize-RagRuntime {
    param([string]$Python)

    Set-DefaultEnv "PYTHONUTF8" "1"
    Set-DefaultEnv "PYTHONIOENCODING" "utf-8"
    Set-DefaultEnv "NO_PROXY" "127.0.0.1,localhost,::1"
    Set-DefaultEnv "no_proxy" "127.0.0.1,localhost,::1"
    Set-DefaultEnv "OMP_NUM_THREADS" "1"
    Set-DefaultEnv "MKL_NUM_THREADS" "1"
    Set-DefaultEnv "OPENBLAS_NUM_THREADS" "1"
    Set-DefaultEnv "NUMEXPR_NUM_THREADS" "1"
    Set-DefaultEnv "TOKENIZERS_PARALLELISM" "false"
    Set-DefaultEnv "MINERU_DEVICE_MODE" "cpu"
    Set-DefaultEnv "MINERU_API_MAX_CONCURRENT_REQUESTS" "1"
    Set-DefaultEnv "MINERU_PROCESSING_WINDOW_SIZE" "1"
    Set-DefaultEnv "MINERU_LOCAL_API_STARTUP_TIMEOUT_SECONDS" "180"
    Set-DefaultEnv "HF_HUB_DISABLE_SYMLINKS_WARNING" "1"
    Set-DefaultEnv "RAG_ANYTHING_COPY_SYMLINK_FALLBACK" "1"

    $InitialPythonCommand = $null
    if ([string]::IsNullOrWhiteSpace($Python) -or $Python -eq "python") {
        $InitialPythonCommand = Get-Command "python.exe" -ErrorAction SilentlyContinue
    }

    $WorkbenchRoot = Resolve-WorkbenchRoot
    if ($WorkbenchRoot) {
        $SharedRagRoot = Join-Path $WorkbenchRoot "07_TOOLS\ai_capabilities\rag"
        $RuntimeRoot = if (-not [string]::IsNullOrWhiteSpace($env:WORKBENCH_RAG_RUNTIME)) {
            $env:WORKBENCH_RAG_RUNTIME
        } else {
            Join-Path $WorkbenchRoot "30_LOCAL_HEAVY\runtime\rag-anything-python312"
        }
        $RuntimeVenv = if (-not [string]::IsNullOrWhiteSpace($env:WORKBENCH_RAG_VENV)) {
            $env:WORKBENCH_RAG_VENV
        } else {
            Join-Path $RuntimeRoot ".venv"
        }
        $RuntimeVenvScripts = Join-Path $RuntimeVenv "Scripts"
        $RuntimePython = if (-not [string]::IsNullOrWhiteSpace($env:WORKBENCH_RAG_PYTHON)) {
            $env:WORKBENCH_RAG_PYTHON
        } else {
            Join-Path $RuntimeVenvScripts "python.exe"
        }
        $LegacyVenvScripts = Join-Path $SharedRagRoot "src\.venv\Scripts"
        $LegacyPython = Join-Path $LegacyVenvScripts "python.exe"
        $PythonStartup = Join-Path $SharedRagRoot "python_startup"
        $CacheRoot = Join-Path $WorkbenchRoot "30_LOCAL_HEAVY\runtime\ai_model_cache"

        Add-PathEntry $RuntimeVenvScripts
        Add-PathEntry $LegacyVenvScripts -Append
        Add-PythonPathEntry $PythonStartup
        Set-DefaultEnv "WORKBENCH_PYTHON_VERSION" "3.12"
        Set-DefaultEnv "WORKBENCH_RAG_RUNTIME" $RuntimeRoot
        Set-DefaultEnv "WORKBENCH_RAG_VENV" $RuntimeVenv
        Set-DefaultEnv "WORKBENCH_RAG_PYTHON" $RuntimePython
        Set-DefaultEnv "HF_HOME" (Join-Path $CacheRoot "huggingface")
        Set-DefaultEnv "HF_HUB_CACHE" (Join-Path $CacheRoot "huggingface\hub")
        Set-DefaultEnv "TORCH_HOME" (Join-Path $CacheRoot "torch")
        Set-DefaultEnv "TIKTOKEN_CACHE_DIR" (Join-Path $CacheRoot "tiktoken")

        if (([string]::IsNullOrWhiteSpace($Python) -or $Python -eq "python") -and
            (Test-Path -LiteralPath $RuntimePython)) {
            $Python = (Resolve-Path -LiteralPath $RuntimePython).Path
        }
        elseif (([string]::IsNullOrWhiteSpace($Python) -or $Python -eq "python") -and
            (Test-Path -LiteralPath $LegacyPython)) {
            $Python = (Resolve-Path -LiteralPath $LegacyPython).Path
        }
    }

    Add-PathEntry (Join-Path $env:ProgramFiles "LibreOffice\program") -Append
    Add-PathEntry (Join-Path ${env:ProgramFiles(x86)} "LibreOffice\program") -Append
    Add-PathEntry (Join-Path $env:ProgramFiles "Pandoc") -Append
    Add-PathEntry (Join-Path $env:LOCALAPPDATA "Pandoc") -Append

    if ([string]::IsNullOrWhiteSpace($Python)) {
        return "python"
    }
    if ($Python -eq "python" -and $InitialPythonCommand) {
        return $InitialPythonCommand.Source
    }
    return $Python
}
