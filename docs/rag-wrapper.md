# External RAG-Anything Wrapper

This repository keeps `HKUDS/RAG-Anything` as a git submodule and adds an
external checker around it. The checker does not register an MCP server, Codex
plugin, or any other Codex integration. It only inspects the submodule, local
Python environment, command-line tools, and runtime `.env` values.

## Files

- `configs/rag-tool-check.toml` - checker policy: required parsers, optional
  tools, env vars, commands, report path.
- `configs/rag-runtime.env.example` - public template for a runtime `.env`.
- `tools/rag_tool_check.py` - dependency-free Python checker.
- `scripts/check-rag-tools.ps1` - Windows launcher.

## Run

From the repository root:

```powershell
.\scripts\check-rag-tools.ps1
```

For a non-failing report during setup:

```powershell
.\scripts\check-rag-tools.ps1 -ReportOnly
```

Direct Python form:

```powershell
python tools\rag_tool_check.py --config configs\rag-tool-check.toml
```

The JSON report is written to `reports/rag-tool-check.json` by default. The
`reports/` directory is ignored by git.

## Configure

1. Copy `configs/rag-runtime.env.example` to `.env`.
2. Replace placeholder values with real local settings and secrets.
3. Edit `configs/rag-tool-check.toml` to decide which parsers and format
   features are hard requirements for your machine.

Examples:

- Require Docling too: add `"docling"` to `policy.required_parsers`.
- Require Office conversion: add `"office"` to
  `policy.required_format_features`.
- Parser-only validation: remove LLM and embedding keys from
  `policy.required_env`.

## What It Checks

- Submodule is present and tracked as a gitlink.
- RAG-Anything parser tools offered by the current revision.
- Modal processors offered by the current revision.
- Optional extras from `pyproject.toml`.
- MinerU CLI, Docling import, PaddleOCR import, PaddlePaddle and PDF renderer.
- LibreOffice, Pillow, ReportLab, Markdown-related extras when relevant.
- Runtime env values for parser selection, parse method, providers, and common
  numeric settings.
- Placeholder secrets and incomplete public asset URL mapping.
- Absence of repo-local MCP/plugin registration artifacts.
