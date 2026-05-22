# Commercial Calculation Pipeline

Initial public repository scaffold for the commercial calculation pipeline.

## RAG-Anything Wrapper

This repo includes `HKUDS/RAG-Anything` as a git submodule and provides a
full-coverage external tool/config checker around it. It does not connect
RAG-Anything to Codex as an MCP server or plugin.

The wrapper architecture is module-based:

- `tools/wrapper_platform/` is the shared registry/launcher layer for external
  wrapper modules.
- `tools/wrapper_modules/rag_anything/` is the RAG-Anything wrapper module.
- `tools/wrapper.py` is the single Python entrypoint for wrapper modules.

Future unrelated scripts should become new siblings under `tools/wrapper_modules/`,
not be added into the RAG module.

Run the checker:

```powershell
.\scripts\check-rag-tools.ps1 -ReportOnly
```

Run the visual console dashboard:

```powershell
.\scripts\show-rag-console.ps1 -ReportOnly
```

The dashboard shows a compact visual map by default. Use `-Details` for full
API/env/export diagnostics, or `-Plain -NoAnimations -NoPause` for log-friendly
output.

See `docs/rag-wrapper.md` for configuration and runtime setup details.
