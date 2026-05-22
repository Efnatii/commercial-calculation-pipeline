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
- `tools/wrapper.py` - single Python launcher for wrapper-platform modules.
- `tools/wrapper_platform/` - shared registry/launcher layer for independent
  external wrapper modules.
- `tools/wrapper_modules/rag_anything/` - the RAG-Anything wrapper module.
  New RAG-specific checks or console panels can live here, but unrelated future
  scripts should become separate sibling modules under `tools/wrapper_modules/`.
- `scripts/check-rag-tools.ps1` - Windows launcher for
  `wrapper.py rag-anything check`.
- `scripts/show-rag-console.ps1` - Windows launcher for
  `wrapper.py rag-anything visual`.

No separate RAG Python shims remain. This RAG module lives under
`wrapper_modules.rag_anything`; the shared module registry lives under
`wrapper_platform`.

Current package layout:

- `wrapper_platform` - module-level API, static registry, and optional generic
  CLI dispatcher for all wrapper modules.
- `wrapper_modules.rag_anything.core` - RAG-module models, config loading, env
  parsing, subprocess helpers, paths, validation, and report writing.
- `wrapper_modules.rag_anything.discovery` - static source inspection of
  RAG-Anything package API, package/example/reproduce CLI surfaces, env
  surface, exports, parsers, processors, pyproject, and formats.
- `wrapper_modules.rag_anything.checks` - one RAG check category per file:
  project, coverage, environment, providers, parsers, processors, formats,
  storage, CLI, API, and smoke checks.
- `wrapper_modules.rag_anything.console` - console models, ANSI palette,
  terminal helpers, progress animations, text wrapping, visual item builders,
  and panel renderers.
- `wrapper_modules.rag_anything.console.panels` - independent dashboard panels
  for summary, maps, category breakdowns, actions, and details.
- `wrapper_modules.rag_anything.commands` - thin RAG command entrypoints for
  `check` and `visual`.
- `wrapper_modules.rag_anything.module` - registers the RAG module and its
  commands with the shared wrapper platform.
- `wrapper_modules.rag_anything.plugins.registry` - RAG-local static registry
  for check plugins, console panel plugins, command descriptors, and fixed
  visual panel order.

Extension points are intentionally static and wrapper-local:

- `CheckPlugin` - adds a discovery/check phase without importing anything from
  `RAG-Anything` dynamically.
- `ConsolePanelPlugin` - reserves stable panel ids and display order for visual
  dashboard blocks.
- `CommandPlugin` - describes future wrapper commands while the public
  PowerShell and Python entrypoints remain stable.

For unrelated future functionality, add a new module package such as
`tools/wrapper_modules/<new_module>/module.py` and register it in
`tools/wrapper_platform/registry.py`. Do not put unrelated scripts inside the
RAG module.

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
python tools\wrapper.py rag-anything check -- --config configs\rag-tool-check.toml
```

Visual dashboard:

```powershell
.\scripts\show-rag-console.ps1 -ReportOnly
```

The dashboard enables Windows virtual-terminal mode before using ANSI colors,
shows progress/spinner animations in interactive terminals, and waits for Enter
before closing. The default view is a compact visual module map; use `-Details`
only when you need full API/env/export diagnostics. Use plain non-pausing mode
for logs:

```powershell
.\scripts\show-rag-console.ps1 -ReportOnly -Plain -NoAnimations -NoPause
```

Full diagnostic view:

```powershell
.\scripts\show-rag-console.ps1 -ReportOnly -Details
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
- Fail whenever RAG-Anything adds a new env key, package/example/reproduce CLI
  arg, export, optional extra, parser, processor, or public package API name:
  keep `coverage.require_full_coverage = true`.

## What It Checks

- Submodule is present and tracked as a gitlink.
- RAG-Anything parser tools offered by the current revision.
- Modal processors offered by the current revision.
- Optional extras from `pyproject.toml`.
- Full coverage of all env keys from `RAG-Anything/env.example` and env reads in
  RAG-Anything code/examples/reproduce scripts.
- CLI coverage for every argparse surface found under `raganything/`,
  `examples/`, and `reproduce/`.
- Package exports and full public package API surface exposed by the current
  `raganything/*.py` files.
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
extra, env key, package/example/reproduce CLI argument, package export, or
public package API name, the checker fails until the wrapper config is updated
intentionally.
