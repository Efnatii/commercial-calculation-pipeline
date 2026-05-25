# Codex Bridge Acceptance Map

This document maps the original implementation goal to the concrete files,
runtime behavior, and verification commands in this repository.

## Requirement Map

| Goal item | Status | Evidence |
| --- | --- | --- |
| Work inside this repository | Done | Bridge source lives under `tools/wrapper_modules/codex_bridge/`; entrypoints are `tools/codex_bridge_app.py`, `tools/codex_bridge_server.py`, and `tools/codex_bridge_cert.py`. |
| Local server for GitHub Pages to interact with Codex | Done | HTTP API in `tools/wrapper_modules/codex_bridge/core/server.py`; OpenAPI contract in `docs/codex-bridge-openapi.json`; CORS allows `https://*.github.io` by default; TLS helper and HTTPS `/health` smoke are verified by `scripts/verify-codex-bridge.ps1`. |
| Ready `.exe` | Done | Single runtime executable built at `dist/codex-bridge.exe` by `scripts/build-codex-bridge-exe.ps1`. |
| Cover Codex interactions broadly | Done | `docs/codex-bridge-codex-cli-coverage.md` maps installed Codex CLI areas to bridge modes; `scripts/check-codex-bridge-coverage.ps1` checks live `codex --help`; backend/UI/OpenAPI expose 59 modes. |
| GitHub Pages UI | Done | Static UI under `docs/codex-ui/`; redirect page in `docs/index.html`; publishing workflow in `.github/workflows/pages.yml`. |
| Separate UI environment/container | Done | Per-workspace `CODEX_HOME` directories under `.codex-bridge/workspaces/<id>/codex-home`; per-workspace path, env, model/profile/sandbox settings in `.codex-bridge/server.json`. |
| Multiple computers/workspaces | Done | Workspace CRUD API and UI allow separate workspace ids and paths; tokens can be scoped to selected workspace ids. |
| Local server graphical interface | Done | Native Windows WebView2/tray app in `tools/wrapper_modules/codex_bridge/core/tray_app.py`; token/workspace/job/settings/audit views in `docs/codex-ui/`. |
| Issue server access tokens | Done | `GET/POST/DELETE /api/tokens`; token store in `.codex-bridge/tokens.json`; UI tab `Tokens`; CLI command module `tools/wrapper_modules/codex_bridge/commands/token.py`. |
| Locked-down token-required launch | Done | `scripts/start-codex-bridge-exe.ps1` requires tokens for headless LAN API access by default; `-RequireTokens` also disables loopback bypass for that run; `scripts/verify-codex-bridge.ps1` checks 403 without a token and authenticated success with the bootstrap admin token. |
| Fit wrapper architecture | Done | Module registered from `tools/wrapper_platform/registry.py`; module metadata in `tools/wrapper_modules/codex_bridge/module.py`. |
| Automated and manual tests | Done | Unit tests in `tests/test_codex_bridge_core.py`; full local suite in `scripts/verify-codex-bridge.ps1`; smoke test in `scripts/smoke-codex-bridge.ps1`; verification report in `docs/codex-bridge-verification.md`. |
| Weak LAN clients do not install Codex | Done | Only the strong machine runs Codex CLI; browser clients use GitHub Pages UI plus a bridge token to call the bridge HTTP API. This is documented in `docs/codex-bridge.md` and `README.md`. |
| Modern lightweight UI with animation | Done | Responsive UI in `docs/codex-ui/index.html`, `docs/codex-ui/styles.css`, and `docs/codex-ui/app.js`; Playwright screenshot smoke checks desktop/mobile layouts. |
| Server UI must not open browser | Done | Native WebView2 window/tray from the same exe; hidden mode verified by `scripts/verify-codex-bridge.ps1 -Native`. |
| Background service/tray behavior | Done | Closing the native window hides it; tray menu controls open/hide/restart/stop/quit; scheduled task helper in `scripts/install-codex-bridge-task.ps1`. |
| Single exe only | Done | Runtime is `dist/codex-bridge.exe`. Operational scripts/docs are packaging helpers, not extra runtime executables. |
| Native Windows web UI, not Qt/Tkinter | Done | Uses `pywebview` on Windows WebView2 and `pystray`; no Qt/Tkinter dependency. |
| OpenAI docs alignment | Done | `docs/codex-bridge.md` records alignment with official Codex CLI and Codex Cloud docs; bridge delegates execution to the installed official Codex CLI. |
| Generated icons/logos | Done | Generated assets in `docs/codex-ui/assets/`; used by UI, favicon, tray, and PyInstaller icon. |
| Server access token, not Codex token | Done | Bridge token model is separate from Codex credentials. Weak clients do not receive Codex tokens. Admin actions require local native UI/loopback or a bridge token with `admin` scope. |

## Current Verification Gate

Run from the repository root:

```powershell
python -m unittest discover -s tests -p "test_codex_bridge*.py"
.\scripts\verify-codex-bridge.ps1 -Ui -Native -Package -PortBase 9200
```

The verified package can be extracted and checked independently:

```powershell
.\scripts\package-codex-bridge-release.ps1 -PackageName codex-bridge-release-20260524
.\artifacts\codex-bridge-release-20260524\scripts\verify-codex-bridge.ps1
```

## Security Boundary Summary

- `security.require_api_tokens=true` by default and headless launcher defaults
  require bridge tokens for LAN API access.
- LAN clients without a bridge token receive `403` by default, including
  `/api/status`.
- The bridge-hosted `/ui` page is denied to LAN clients by default; weak
  clients should use the GitHub Pages UI with a bridge token.
- `/health` is loopback-only by default; LAN clients should use authenticated
  `/api/status`.
- Legacy LAN no-token access is available only when
  `security.allow_lan_without_token=true` is explicitly configured or launched,
  and then only for scopes listed in `security.no_auth_scopes`.
- Loopback/native UI can administer the bridge by default through
  `security.allow_loopback_admin_without_token=true`.
- Bearer bridge tokens are honored even when legacy no-token mode is explicitly
  enabled, so selected LAN users can receive `admin` access without Codex
  credentials.
- `-RequireTokens` forces bearer tokens for every non-health API request in
  both headless and native launcher modes, including loopback requests.

## Operational Handoff

Primary runtime:

```text
dist/codex-bridge.exe
```

Primary release package:

```text
artifacts/codex-bridge-release-20260524.zip
```

Typical strong-machine launch:

```powershell
.\scripts\start-codex-bridge-exe.ps1 -NativeUi -Hidden -HostOverride 0.0.0.0 -Port 8765
```

Weak clients open:

```text
https://<owner>.github.io/<repo>/codex-ui/
```

In that GitHub Pages UI, set Bridge URL to:

```text
http://<strong-machine-ip>:8765
```

For HTTPS GitHub Pages clients, generate and trust a local certificate first:

```powershell
.\scripts\new-codex-bridge-cert.ps1 -HostName <strong-machine-ip> -HostName <strong-machine-name>
```

The release package includes `tools/codex_bridge_cert.py`, which is required by
that certificate helper.
