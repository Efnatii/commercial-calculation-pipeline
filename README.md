# Commercial Calculation Pipeline

Initial public repository scaffold for the commercial calculation pipeline.

## RAG-Anything Wrapper

This repo includes `HKUDS/RAG-Anything` as a git submodule and provides a
full-coverage external tool/config checker around it. It does not connect
RAG-Anything to Codex as an MCP server or plugin.

Run the checker:

```powershell
.\scripts\check-rag-tools.ps1 -ReportOnly
```

Run the visual console dashboard:

```powershell
.\scripts\show-rag-console.ps1 -ReportOnly
```

See `docs/rag-wrapper.md` for configuration and runtime setup details.
