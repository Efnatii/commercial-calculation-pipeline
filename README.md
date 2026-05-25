# Commercial Calculation Pipeline

Initial public repository scaffold for the commercial calculation pipeline.

## RAG-Anything Wrapper

This repo includes `HKUDS/RAG-Anything` as a git submodule and provides a
full-coverage external tool/config checker around it. It does not connect
RAG-Anything to Codex as an MCP server or plugin.

The checker now has two layers: static coverage/config checks and safe real
runtime smoke probes. The smoke layer actually imports RAG-Anything, creates
config and wrapper objects, exercises parser registry/callback/processor APIs,
runs a batch dry-run on a temporary TXT file, and starts safe CLI `--help`
commands without using network services or external storage.

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

## Codex Bridge

This repo also includes a new `codex-bridge` wrapper module: one native Windows
tray executable that runs a local HTTP bridge in the background, plus a static
GitHub Pages UI for submitting Codex CLI jobs to one stronger LAN machine.

Initialize and run it locally:

```powershell
.\scripts\start-codex-bridge.ps1 -Init
```

Then open:

```text
http://127.0.0.1:8765/ui
```

Build the one-file Windows executable:

```powershell
.\scripts\build-codex-bridge-exe.ps1
```

Run the native tray/server app:

```powershell
.\dist\codex-bridge.exe
```

Run the native tray/server app hidden in the tray:

```powershell
.\scripts\start-codex-bridge-exe.ps1 -NativeUi -Hidden
```

Weak LAN clients do not need Codex credentials, but they do need a bridge
Bearer token. Direct LAN access to the bridge API and the bridge-hosted `/ui`
page is denied by default. Issue user tokens from the local native UI on the
strong machine, then let weak clients use the GitHub Pages UI with the strong
machine bridge URL.

Run the same executable headlessly for automation:

```powershell
.\scripts\start-codex-bridge-exe.ps1
```

Package the executable, UI, docs, checksums, and run scripts for handoff:

```powershell
.\scripts\package-codex-bridge-release.ps1
```

Optional LAN setup helpers:

```powershell
.\scripts\new-codex-bridge-cert.ps1 -HostName 192.168.1.10
.\scripts\open-codex-bridge-firewall.ps1 -Port 8765
.\scripts\install-codex-bridge-task.ps1 -NativeUi -Hidden
```

Verify the bridge:

```powershell
.\scripts\verify-codex-bridge.ps1
.\scripts\smoke-codex-bridge.ps1
.\scripts\smoke-codex-bridge.ps1 -UseExe
```

See `docs/codex-bridge.md`, `docs/codex-bridge-architecture.md`,
`docs/codex-bridge-codex-cli-coverage.md`,
`docs/codex-bridge-acceptance.md`, `docs/codex-bridge-verification.md`, and
`docs/codex-bridge-openapi.json` for API, token, workspace, GitHub Pages,
network/TLS, Codex CLI coverage, and architecture notes.
