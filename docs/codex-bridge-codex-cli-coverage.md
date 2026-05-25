# Codex CLI Coverage

This matrix records how `codex-bridge` exposes the installed Codex CLI to LAN
browser clients. The bridge API and the GitHub Pages/native UI mode selector
are kept in parity by `test_static_ui_exposes_all_backend_modes`.
`scripts/check-codex-bridge-coverage.ps1` also compares this matrix and the
bridge mode set with the currently installed `codex --help` top-level and
nested subcommands when Codex CLI is available.

| Codex command area | Bridge mode | Scope | Notes |
| --- | --- | --- | --- |
| `codex exec` | `exec` | `run` | Non-interactive JSONL job output; supports prompt, model, sandbox, search, images. |
| `codex exec resume` | `exec-resume` | `run` | Non-interactive resume by id or `--last`. |
| `codex resume` | `resume` | `run` | Interactive-style CLI is wrapped as a cancellable job with `--no-alt-screen`. |
| `codex fork` | `fork` | `run` | Interactive-style CLI is wrapped as a cancellable job with `--no-alt-screen`. |
| `codex review` | `review` | `run` | Runs code review from the workspace. |
| `codex doctor` | `doctor` | `run` | JSON diagnostic output. |
| `codex login status` | `login-status` | `run` | Read-only auth status. |
| `codex login --with-api-key` | `login-api-key` | `admin` | Secret is passed through stdin and not logged as a command arg. |
| `codex login --with-access-token` | `login-access-token` | `admin` | Secret is passed through stdin and not logged as a command arg. |
| `codex login --device-auth` | `login-device-auth` | `admin` | Starts Codex device auth as a cancellable job. |
| `codex logout` | `logout` | `admin` | Removes credentials in workspace `CODEX_HOME`. |
| `codex mcp list/get` | `mcp-list`, `mcp-get` | `run` | Read configured MCP servers. |
| `codex mcp add/remove/login/logout` | `mcp-add`, `mcp-remove`, `mcp-login`, `mcp-logout` | `admin` | Mutates workspace Codex MCP config/auth. |
| `codex plugin list` | `plugin-list` | `run` | Lists available plugins. |
| `codex plugin add/remove` | `plugin-add`, `plugin-remove` | `admin` | Mutates plugin config/cache. |
| `codex plugin marketplace ...` | `plugin-marketplace-*` | `run`/`admin` | List is read-only; add/remove/upgrade are admin-only. |
| `codex features list` | `features-list` | `run` | Read feature flags. |
| `codex features enable/disable` | `features-enable`, `features-disable` | `admin` | Mutates workspace config. |
| `codex app-server daemon ...` | `app-daemon-*` | `run`/`admin` | Version is read-only; start/restart/stop/remote-control are admin-only. |
| `codex remote-control ...` | `remote-start`, `remote-stop` | `admin` | Starts/stops remote-control daemon. |
| `codex apply` | `apply` | `admin` | Applies a Codex task diff locally. |
| `codex update` | `update` | `admin` | Updates the installed Codex CLI on the strong machine. |
| `codex completion` | `completion` | `run` | Generates shell completions. |
| `codex debug models/prompt-input/app-server send-message-v2` | `debug-models`, `debug-prompt-input`, `debug-app-server-send-message-v2` | `run` | Read/debug outputs as job logs. |
| `codex cloud list/status/diff` | `cloud-list`, `cloud-status`, `cloud-diff` | `run` | Requires Codex Cloud auth in workspace `CODEX_HOME`. |
| `codex cloud exec/apply` | `cloud-exec`, `cloud-apply` | `admin` | Submits/applies cloud work. |
| `codex sandbox linux/macos/windows` | `sandbox-linux`, `sandbox-macos`, `sandbox-windows` | `admin` | Runs an explicit command under a Codex sandbox. |
| `codex exec-server` | `exec-server-start` | `admin` | Long-running job, cancellable through `/api/jobs/{id}/cancel`. |
| `codex mcp-server` | `mcp-server` | `admin` | Starts stdio MCP server mode as a cancellable job. |
| `codex app` | `app-open` | `admin` | Launches Codex Desktop on the strong machine for the chosen workspace path. |
| `codex app-server` | `app-server-start` | `admin` | Long-running app server, cancellable through `/api/jobs/{id}/cancel`. |
| `codex app-server proxy` | `app-server-proxy` | `admin` | Proxies stdio to an existing app-server socket. |
| `codex app-server generate-*` | `app-server-generate-ts`, `app-server-generate-json-schema` | `admin` | Writes generated protocol files to an admin-chosen output directory. |
| `codex help` and subcommand help | `help` | `run` | Whitelisted help topics. |
| Raw Codex args | `raw` | `admin` | Disabled by default via `security.allow_raw_codex_args=false`. |

Operational notes:

- Service-style modes such as `mcp-server`, `app-server-start`,
  `app-server-proxy`, and `exec-server-start` are exposed as long-running jobs
  so an administrator can cancel them from the Jobs view.
- `app-open` launches UI on the strong machine, not on the weak LAN client.
- Fully interactive TUI picker flows without `--last` or an id can hang in a
  non-terminal job. Prefer `exec`, `exec-resume`, explicit ids, or cancellable
  jobs.
