# External RAG-Anything Wrapper

This repository keeps `HKUDS/RAG-Anything` as a git submodule and adds an
external checker around it. The checker does not register an MCP server, Codex
plugin, or any other Codex integration. It only inspects the submodule, local
Python environment, command-line tools, runtime `.env` values, and the coverage
manifest in `configs/rag-tool-check.toml`.

## Files

- `configs/rag-tool-check.toml` - full coverage manifest and checker policy:
  parsers, processors, optional extras, every discovered env key, storage
  backends, provider settings, CLI arguments, public API methods, package
  exports, commands, and smoke-test toggles.
- `configs/rag-runtime.env.example` - public template for a runtime `.env`
  matching the coverage manifest.
- `tools/rag_tool_check.py` - dependency-free Python checker.
- `tools/rag_visual_console.py` - visual console dashboard built on the same
  checker report.
- `scripts/check-rag-tools.ps1` - Windows launcher.
- `scripts/show-rag-console.ps1` - Windows launcher for the visual dashboard.

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

Visual dashboard:

```powershell
.\scripts\show-rag-console.ps1 -ReportOnly
```

The dashboard uses plain text by default so Windows consoles do not show raw
ANSI escape codes. Enable color only in terminals that render ANSI correctly:

```powershell
.\scripts\show-rag-console.ps1 -ReportOnly -Color
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
- Fail whenever RAG-Anything adds a new env key, CLI arg, export, optional
  extra, parser, processor, or public API method not represented in the wrapper:
  keep `coverage.require_full_coverage = true`.

## What It Checks

- Submodule is present and tracked as a gitlink.
- RAG-Anything parser tools offered by the current revision.
- Modal processors offered by the current revision.
- Optional extras from `pyproject.toml`.
- Full coverage of all env keys from `RAG-Anything/env.example` and env reads in
  RAG-Anything code/examples/reproduce scripts.
- CLI coverage for `raganything.parser`, `raganything.batch_parser`, and
  `raganything.enhanced_markdown`.
- Package exports and public API methods exposed by the current revision.
- Storage backend configuration surfaces: PostgreSQL, Neo4j, AGE, TiDB,
  MongoDB, Milvus, Qdrant, and Redis.
- MinerU CLI, Docling import, PaddleOCR import, PaddlePaddle and PDF renderer.
- LibreOffice, Pillow, ReportLab, Markdown-related extras, Pandoc, and provider
  tools when relevant.
- Runtime env values for parser selection, parse method, providers, and common
  numeric, boolean, URL, path, enum, paired-key, and comma-list settings.
- Placeholder secrets and incomplete public asset URL mapping.
- Absence of repo-local MCP/plugin registration artifacts.

## Coverage Gate

The `coverage` section is the important guardrail. With
`require_full_coverage = true`, the checker compares the config against the
current RAG-Anything submodule. If upstream adds a parser, processor, optional
extra, env key, CLI argument, package export, or public API method, the checker
fails until the wrapper config is updated intentionally.
