# Codex Bridge Verification

Verified on 2026-05-24 in the local Windows workspace:

```text
C:\__SHARED_FOLDER__\__GIT__\commercial-calculation-pipeline
```

Installed Codex CLI:

```text
codex-cli 0.133.0
```

## Automated Checks

| Check | Result |
| --- | --- |
| `python -m unittest discover -s tests -p "test_codex_bridge*.py"` | 23 tests OK |
| `python -W error::ResourceWarning -m unittest discover -s tests -p "test_codex_bridge*.py"` | OK |
| `python -m compileall -q tools\wrapper_modules\codex_bridge tools\codex_bridge_server.py tools\codex_bridge_app.py tools\codex_bridge_cert.py` | OK |
| `node --check docs\codex-ui\app.js` | OK |
| `python -c "import json; json.load(open('docs/codex-bridge-openapi.json', encoding='utf-8'))"` | OK |
| `scripts\check-codex-bridge-coverage.ps1` | OK, 22 installed Codex top-level commands and 13 nested help paths covered |
| PowerShell parser over `scripts/*.ps1` | OK |
| `scripts\smoke-codex-bridge.ps1 -Port 8811` | OK |
| `scripts\smoke-codex-bridge.ps1 -UseExe -Port 8812` | OK |
| `scripts\verify-codex-bridge.ps1 -BuildExe -Ui -Native -Package -PortBase 8870` | OK |
| `scripts\verify-codex-bridge.ps1 -Ui -Native -Package -PortBase 8900` | OK, including start-script headless/native UI smoke |
| `scripts\verify-codex-bridge.ps1 -Ui -Native -Package -PortBase 8920` | OK, including live Codex CLI coverage and `-NativeUi -Hidden` launcher smoke |
| `scripts\verify-codex-bridge.ps1 -Ui -Native -Package -PortBase 8970` | OK, after rebuilding the executable with GitHub Pages CORS pattern support |
| Scheduled task dry run | OK, hidden native autostart arguments validated without registering a task |
| `scripts\verify-codex-bridge.ps1 -Ui -Native -Package -PortBase 9040` | OK, after adding `login-device-auth` and nested Codex CLI help coverage |
| Backend/UI/OpenAPI mode parity | OK, exact 59-mode equality checked by unit tests |
| LAN no-token boundary | OK, no-token LAN gets 403 by default for `/api/status`; legacy read/run requires explicit `allow_lan_without_token`; bearer admin token still works |
| Direct LAN `/ui` boundary | OK, bridge-hosted `/ui` returns 403 for non-loopback clients unless `allow_lan_static_ui=true` is explicitly configured |
| Runtime `0.0.0.0:8765` LAN access check | OK, `192.168.100.5` and `192.168.137.1` return 403 for `/health`, `/api/status`, and `/ui` without a token; `/api/status` returns 200 with a bridge token |
| `scripts\verify-codex-bridge.ps1 -Ui -Native -Package -PortBase 9120` | OK, after final bridge-server-token UI copy and embedded one-file rebuild |
| `scripts\verify-codex-bridge.ps1 -Ui -Native -Package -PortBase 9200` | OK, after adding explicit mode-scope and LAN admin-job boundary tests |
| `scripts\verify-codex-bridge.ps1 -Ui -Native -Package -PortBase 9300` | OK, after adding explicit acceptance mapping to the release package |
| Headless `-RequireTokens` launch smoke | OK, no-token `/api/status` returns 403, bootstrap admin token is created, authenticated `/api/status` succeeds |
| `scripts\verify-codex-bridge.ps1 -Ui -Native -Package -PortBase 9600` | OK, after fixing Windows UTF-8 BOM config loading and strict `-RequireTokens` loopback behavior |
| `scripts\verify-codex-bridge.ps1 -Ui -Native -Package -PortBase 9800` | OK, after adding package manifest size/SHA verification |
| `scripts\verify-codex-bridge.ps1 -Ui -Native -Package -PortBase 10100` | OK, after adding release-packaged certificate helper and HTTPS `/health` smoke |
| `scripts\verify-codex-bridge.ps1 -Ui -Native -Package -PortBase 10400` | OK, after fixing release compatibility launcher delegation when `tools\wrapper.py` is absent |
| TCP port availability preflight | OK, reports listening owner processes before smoke tests if a selected `-PortBase` range is busy |
| `scripts\verify-codex-bridge.ps1 -Ui -Native -Package -PortBase 11100` | OK, after adding TCP port availability preflight |
| `scripts\verify-codex-bridge.ps1 -Ui -Native -Package -PortBase 11200` | OK, after adding example-config and workflow trigger coverage |
| `npx --yes prettier --check ".github/workflows/*.yml" "docs/**/*.html" "docs/**/*.css" "docs/**/*.js"` | OK |
| `scripts\verify-codex-bridge.ps1 -Ui -Native -Package -PortBase 11300` | OK, after UI/workflow formatting and release-specific package README |
| Workflow trigger and formatting coverage | OK, unit-tested and enforced in GitHub Actions plus local `verify-codex-bridge.ps1` |
| Release package root `README.md` | OK, package-mode verification requires `# Codex Bridge Release` and rejects the source repository RAG section |
| `scripts\verify-codex-bridge.ps1 -Ui -Native -Package -PortBase 11400` | OK, after moving formatting and release-README checks into automation |
| Backend/OpenAPI API path parity | OK, unit-tested for documented backend endpoints including `/api/codex/doctor` and `/api/codex/review` |
| `scripts\verify-codex-bridge.ps1 -Ui -Native -Package -PortBase 11500` | OK, after documenting Codex convenience endpoints and closing job stdout pipes |
| `scripts\verify-codex-bridge.ps1 -Ui -Native -Package -PortBase 11600` | OK, after locking down LAN no-token API access and direct bridge-hosted LAN `/ui` access |
| `scripts\verify-codex-bridge.ps1 -Ui -Native -Package -PortBase 11900` | OK, after making `/health` loopback-only for LAN clients by default |

Smoke result summary:

```json
{
  "codex_version": "codex-cli 0.133.0",
  "modes": 59,
  "help_job_status": "completed",
  "workspace_count": 1
}
```

## UI Checks

Playwright/Edge opened the browser UI from loopback bridge server and waited
for `.status-pill.is-online` on both viewport sizes:

- Desktop: `1440x960`
- Mobile: `390x844`

Screenshots were saved locally under:

```text
.codex-bridge/playwright/
```

Checked screens:

- connection panel with bridge server token field;
- mode/workspace controls;
- responsive mobile layout;
- live output panel;
- no obvious text overlap after resizing.

The API CORS path was also checked by unit test with
`Origin: https://example.github.io`; the server returned the same origin
through `Access-Control-Allow-Origin` via the default
`server.allowed_origin_patterns=["https://*.github.io"]`.

The native Windows mode was started both hidden and visible from the same
executable. Hidden tray mode answered `/health` while no browser was opened.
Visible mode answered `/health` and a `Codex Bridge` WebView2 window was found
through Win32 window enumeration.

The app logo was generated with the built-in `image_gen` tool and saved into
`docs/codex-ui/assets/`. The generated icon is used by the browser UI, favicon,
tray icon, and PyInstaller executable icon.

## Executable

Final executable:

```text
dist/codex-bridge.exe
```

Size:

```text
23038046 bytes
```

SHA-256:

```text
5aec6619a4e2f99c8c007d5f1546e474e0e6b18f1f4f02a7a32e092672308ee1
```

The executable passed startup and job execution through:

```powershell
.\scripts\smoke-codex-bridge.ps1 -UseExe -Port 8812
```

No leftover bridge server processes were present after smoke tests.

## Release Package

Package folder:

```text
artifacts/codex-bridge-release-20260524
```

Package ZIP:

```text
artifacts/codex-bridge-release-20260524.zip
```

The ZIP contains 34 files: the runtime executable, static UI, generated icon
assets, acceptance map, docs, start scripts, certificate/firewall/task helpers,
`scripts/check-codex-bridge-coverage.ps1`, `scripts/verify-codex-bridge.ps1`,
`tools/codex_bridge_cert.py`, `MANIFEST.json`, root `README.md`, and
`RELEASE_README.md`. Both readme files are release-specific bridge handoff
instructions, not the broader repository README.
`MANIFEST.json` lists 33 payload files and intentionally excludes itself from
its own SHA-256 list; `scripts/verify-codex-bridge.ps1` checks this metadata,
every listed file size, every listed file hash, and the acceptance map entry.
The manifest SHA-256 for `dist/codex-bridge.exe` was checked against the built
executable.

The ZIP was extracted to:

```text
.codex-bridge/verify-final-package
```

Then the extracted bundle passed its package-mode verification path:

```powershell
.\scripts\verify-codex-bridge.ps1 -PortBase 11000
```

In package mode, source checks are skipped because the release archive does not
ship `tools/` and `tests/`; executable smoke, OpenAPI JSON, PowerShell parser,
live Codex CLI coverage, and cleanup checks still run.

## Known Operational Notes

- GitHub Pages origins under `https://*.github.io` are allowed by default.
  Browser clients should use bridge TLS for production LAN access and send a
  Codex Bridge bearer token.
- Direct bridge-hosted `/ui` access from LAN clients is disabled by default.
  Use GitHub Pages UI for weak clients, or explicitly set
  `security.allow_lan_static_ui=true` when direct LAN UI exposure is intended.
- Bridge bearer tokens are required for LAN API access by default. No-token LAN
  API access requires explicit `security.allow_lan_without_token=true` and is
  limited to `security.no_auth_scopes`.
- The bridge isolates Codex state with per-workspace `CODEX_HOME` directories;
  it is not a Docker/Hyper-V container.
- The strong machine must have Codex CLI installed and authenticated for real
  agent jobs.
- The native window uses Microsoft Edge WebView2; install the WebView2 Runtime
  if it is missing on the strong machine.
