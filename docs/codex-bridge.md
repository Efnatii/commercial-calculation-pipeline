# Codex Bridge

`codex-bridge` is a local LAN gateway for running the installed Codex CLI on one
strong machine while lightweight browser clients use a static UI. The local
server itself is managed by a native Windows tray UI from the same executable.

The bridge is intentionally local-first:

- HTTP API is served by the local machine.
- The local server console is a native Windows WebView2 window with a tray icon.
- GitHub Pages can host the same static UI from `docs/codex-ui`.
- Runtime state, tokens, logs, and per-workspace `CODEX_HOME` folders live under
  `.codex-bridge/`, which is local-only.
- Each workspace can have its own path, `CODEX_HOME`, profile, sandbox, env, and
  allowlisted additional directories.

## Start Locally With Native UI

Build the single executable:

```powershell
.\scripts\build-codex-bridge-exe.ps1
```

Run it normally to open the native tray console and start the background server:

```powershell
.\dist\codex-bridge.exe
```

Closing the native window hides it to the tray. The server keeps running until
you stop it from the tray menu or quit the tray app.

Start the same native tray/server mode hidden, useful for logon tasks where the
server should come up in the background and the window should be opened later
from the tray icon:

```powershell
.\scripts\start-codex-bridge-exe.ps1 -NativeUi -Hidden -HostOverride 0.0.0.0 -Port 8765
```

Run the same executable headlessly for scheduled tasks or smoke tests:

```powershell
.\scripts\start-codex-bridge-exe.ps1 -HostOverride 0.0.0.0 -Port 8765
```

Open the local browser UI on the strong machine:

```text
http://127.0.0.1:8765/ui
```

Weak LAN clients should use the GitHub Pages UI and point its Bridge URL field
at the strong machine base URL, for example `http://192.168.1.10:8765`. They do
not need Codex credentials, but they do need a Codex Bridge bearer token issued
from the local native UI on the strong machine. Direct LAN access to the
bridge-hosted `/ui` page is disabled by default.

The default security profile requires bearer tokens for LAN API callers while
allowing the local native/loopback UI to administer the bridge. Launch with
`--require-tokens` when every non-health API call must require a bridge token,
including loopback calls. For the packaged launcher, `-RequireTokens` works in
both native and headless mode:

```powershell
.\scripts\start-codex-bridge-exe.ps1 -RequireTokens -HostOverride 0.0.0.0 -Port 8765
.\scripts\start-codex-bridge-exe.ps1 -NativeUi -Hidden -RequireTokens -HostOverride 0.0.0.0 -Port 8765
```

For source-only development without the executable:

```powershell
.\scripts\start-codex-bridge.ps1 -Init -HostOverride 0.0.0.0 -Port 8765
```

Review `.codex-bridge/server.json` before exposing it beyond loopback:

- GitHub Pages origins matching `https://*.github.io` are allowed by default
  through `server.allowed_origin_patterns`.
- Add a custom Pages/domain origin to `server.allowed_origins` if this
  repository is published under a different host.
- Keep `security.allow_lan_without_token=false` unless you intentionally want
  legacy unauthenticated LAN API calls.
- Keep `security.allow_lan_static_ui=false` unless you intentionally want the
  bridge to serve its own `/ui` page to LAN clients.
- Keep `security.allow_lan_health=false` unless external health monitoring on
  the LAN is intentional.
- Keep `security.allow_danger_full_access` and `security.allow_raw_codex_args`
  disabled unless the machine is isolated.

## API Surface

By default, LAN clients must send `Authorization: Bearer <token>` for every
`/api/*` request except `/health`. The local native WebView2 UI on the strong
machine is trusted through loopback so it can issue and manage those tokens.
The local UI can also call loopback-only `GET /api/local-user-token` to show
the current process bootstrap admin token. This token is regenerated on every
server start and saved to `.codex-bridge/bootstrap-admin-token.txt`; LAN clients
cannot use that endpoint.
User-facing workspace access is name-scoped: the UI sends
`X-Codex-Bridge-User`, workspaces can store an `owner` name, and non-admin
tokens only see owned/unowned workspaces that also pass their token workspace
allowlist.
Legacy no-token LAN API access is only available when
`security.allow_lan_without_token=true`; direct bridge-hosted LAN `/ui` access
is only available when `security.allow_lan_static_ui=true`. `/health` is
loopback-only by default; LAN clients should use authenticated `/api/status`.

Main endpoints:

- `GET /health`
- `GET /api/status`
- `GET /api/capabilities`
- `GET /api/workspaces`
- `POST /api/workspaces` with admin scope
- `GET /api/workspaces/{id}/codex-config` with admin scope
- `POST /api/workspaces/{id}/codex-config` with admin scope
- `GET /api/local-user-token` from loopback only
- `GET /api/chats`
- `POST /api/chats`
- `GET /api/tokens` with admin scope
- `POST /api/tokens` with admin scope
- `GET /api/jobs`
- `POST /api/jobs`
- `GET /api/jobs/{id}`
- `GET /api/jobs/{id}/events?since=0`
- `GET /api/jobs/{id}/stream?since=0`
- `POST /api/jobs/{id}/cancel`
- `GET /api/audit?limit=100` with admin scope
- `POST /api/codex/doctor`
- `POST /api/codex/review`

Machine-readable API contract:

```text
docs/codex-bridge-openapi.json
```

Architecture note:

```text
docs/codex-bridge-architecture.md
```

Codex CLI coverage matrix:

```text
docs/codex-bridge-codex-cli-coverage.md
```

Verification report:

```text
docs/codex-bridge-verification.md
```

Supported job modes are intentionally kept in backend/UI/OpenAPI parity by the
test suite. The full, checked mapping is in
`docs/codex-bridge-codex-cli-coverage.md`. Main groups:

- `exec`: runs `codex exec --json`.
- `exec-resume`: runs `codex exec resume --json`.
- `review`: runs `codex review`.
- `doctor`: runs `codex doctor --json`.
- `login-status`: runs `codex login status`.
- `login-api-key` and `login-access-token`: read a secret from request body and
  pass it to Codex stdin. Admin-only.
- `login-device-auth`: starts Codex device authentication. Admin-only.
- `logout`: runs `codex logout`. Admin-only.
- `mcp-list`: runs `codex mcp list --json`.
- `mcp-get`: runs `codex mcp get --json <name>`.
- `mcp-add`, `mcp-remove`, `mcp-login`, `mcp-logout`. Admin-only.
- `plugin-list`: runs `codex plugin list`.
- `plugin-add`, `plugin-remove`. Admin-only.
- `plugin-marketplace-list`, `plugin-marketplace-add`,
  `plugin-marketplace-remove`, `plugin-marketplace-upgrade`.
- `features-list`: runs `codex features list`.
- `features-enable`, `features-disable`. Admin-only.
- `app-daemon-version`: runs `codex app-server daemon version`.
- `app-daemon-start`, `app-daemon-restart`, `app-daemon-stop`.
- `app-daemon-enable-remote`, `app-daemon-disable-remote`.
- `remote-start` and `remote-stop`: wrap `codex remote-control`.
- `help`: runs whitelisted `codex ... --help` topics.
- `raw`: disabled by default and gated by `security.allow_raw_codex_args`.

Admin-only modes are every mode whose entry in
`docs/codex-bridge-codex-cli-coverage.md` has scope `admin`. That includes
local mutations, auth changes, MCP/plugin/config writes, service start/stop
commands, cloud submit/apply, sandbox commands, raw args, and generated output
writes. The unit test `test_openapi_mode_enum_matches_backend_modes` verifies the
published OpenAPI enum stays equal to the backend mode registry.

## HTTPS For GitHub Pages

GitHub Pages is HTTPS. Modern browsers can block requests from an HTTPS page to
plain HTTP services on private LAN addresses. For LAN use from a published
GitHub Pages UI, generate a local certificate and run the bridge with TLS:

```powershell
.\scripts\new-codex-bridge-cert.ps1 -HostName 192.168.1.10 -HostName strong-pc
.\scripts\start-codex-bridge-exe.ps1 -HostOverride 0.0.0.0 -Port 8765
```

The cert/key are written under `.codex-bridge/tls/`, and `server.tls` in
`.codex-bridge/server.json` is enabled. Trust the generated certificate on the
client machines, then set the GitHub Pages UI Bridge URL to:

```text
https://<strong-machine-ip>:8765
```

For first setup, open the local UI on the strong machine itself:

```text
http://127.0.0.1:8765/ui
```

## GitHub Pages

The static UI lives in:

```text
docs/codex-ui/
```

Configure GitHub Pages to serve from `docs/` and open:

```text
https://<owner>.github.io/<repo>/codex-ui/
```

The repository includes `.github/workflows/pages.yml`, which publishes `docs/`
through GitHub Pages on pushes to `main`.

Browser security matters. A public HTTPS page may not be allowed to call a
plain HTTP server on a private LAN address. The bridge already emits CORS and
Private Network Access headers and allows `https://*.github.io` origins by
default, but production LAN use should prefer one of:

- Use the GitHub Pages UI and a bridge token.
- Enable TLS in `server.tls` and trust the certificate on client machines.
- Use loopback during development: `http://127.0.0.1:8765`.

## Build `.exe`

Build a single-file Windows executable with PyInstaller:

```powershell
.\scripts\build-codex-bridge-exe.ps1
```

Output goes to:

```text
dist/codex-bridge.exe
```

This is the only runtime executable. Normal launch opens the native tray UI;
`--headless` runs the same executable without the native window.

The native UI uses Microsoft Edge WebView2 through the Windows WebView stack.
Current Windows 10/11 installations normally include it; install the WebView2
Runtime on the strong machine if the native window does not open.

Create a handoff package with the executable, UI, docs, run scripts, manifest,
and SHA-256 checksums:

```powershell
.\scripts\package-codex-bridge-release.ps1
```

Packages are written under `artifacts/codex-bridge-release-*`.

The executable still expects the Codex CLI to be installed and authenticated on
the strong machine.

## OpenAI Docs Alignment

The bridge intentionally delegates execution to the official installed Codex CLI
instead of reimplementing Codex behavior. OpenAI's Codex CLI docs describe the
CLI as a local coding agent that can read, change, and run code in the selected
directory, and say first-run authentication is handled by signing in with
ChatGPT or an API key:

```text
https://developers.openai.com/codex/cli
```

That is why this bridge keeps Codex authentication on the strong machine and
does not require weak LAN clients to install Codex or hold Codex credentials.
The separate workspace `CODEX_HOME` folders mirror the environment separation
recommended by Codex configuration and cloud-environment docs without moving
work execution off the strong machine:

```text
https://developers.openai.com/codex/cloud
```

Run the built executable for LAN clients:

```powershell
.\scripts\start-codex-bridge-exe.ps1
```

On first run, the executable can create `.codex-bridge/server.json` itself.
Python is only needed for development scripts and certificate generation.

Install the bridge as a user-level Windows scheduled task:

```powershell
.\scripts\install-codex-bridge-task.ps1
```

Install the native tray/server task hidden at logon:

```powershell
.\scripts\install-codex-bridge-task.ps1 -NativeUi -Hidden
```

Preview the scheduled task command without registering it:

```powershell
.\scripts\install-codex-bridge-task.ps1 -NativeUi -Hidden -DryRun
```

Remove the task:

```powershell
.\scripts\uninstall-codex-bridge-task.ps1
```

## Isolation Model

This is a practical local container, not a Docker container:

- `.codex-bridge/workspaces/<id>/codex-home` isolates Codex config/session state
  per workspace.
- Workspace paths are explicitly configured.
- Extra writable directories are denied unless allowlisted.
- Bearer tokens can be restricted to specific workspace ids.
- LAN clients without a bridge token are denied by default.
- Legacy LAN no-token access requires `security.allow_lan_without_token=true`
  and is limited to `security.no_auth_scopes`.
- Local loopback/native UI can administer the bridge without a token by default
  through `security.allow_loopback_admin_without_token=true`.
- Dangerous sandbox and raw CLI passthrough are disabled by default.
- The admin UI can edit each workspace's
  `.codex-bridge/workspaces/<id>/codex-home/config.toml` independently.
- Workspace-level `env` can pin a local provider, model config, MCP launcher
  variables, or other AI tool settings without exposing the whole workbench.

For stricter isolation, run the `.exe` under a dedicated Windows account and
point workspaces at directories owned by that account.

## Multi-PC LAN Layout

Recommended layout:

```text
Strong machine
  Codex CLI installed and authenticated
  codex-bridge.exe running in tray mode or --headless on 0.0.0.0:8765
  workspaces configured under .codex-bridge/workspaces/*

Weak LAN clients
  browser only
  open the GitHub Pages UI
  set Bridge URL to http://<strong-machine-ip>:8765
  use a bridge token issued on the strong machine
```

Do not install Codex on the weak machines. They only need network access to the
bridge URL.

The Settings page shows detected LAN bridge URLs. If Windows Firewall blocks
access, allow inbound TCP traffic to the chosen bridge port for the private
network.

Helper script, run from an elevated PowerShell on the strong machine:

```powershell
.\scripts\open-codex-bridge-firewall.ps1 -Port 8765
```

## Verification

Run the bridge unit tests:

```powershell
.\scripts\test-codex-bridge.ps1
```

Run the full local verification suite:

```powershell
.\scripts\verify-codex-bridge.ps1 -Ui -Native -Package
```

Check live Codex CLI command coverage against the installed `codex --help`:

```powershell
.\scripts\check-codex-bridge-coverage.ps1
```

Run a local smoke check:

```powershell
.\scripts\start-codex-bridge.ps1 -Init
curl.exe http://127.0.0.1:8765/health
```

Run the full bridge smoke script:

```powershell
.\scripts\smoke-codex-bridge.ps1
.\scripts\smoke-codex-bridge.ps1 -UseExe
```
