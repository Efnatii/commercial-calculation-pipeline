from __future__ import annotations

import json
import os
import shutil
import shlex
import subprocess
from pathlib import Path
from typing import Any

from wrapper_modules.codex_bridge.core.config import BridgeConfig, WorkspaceConfig


ALLOWED_SANDBOXES = {"read-only", "workspace-write", "danger-full-access"}
ALLOWED_APPROVALS = {"never", "on-request", "untrusted"}
ALLOWED_MODES = {
    "exec",
    "exec-resume",
    "resume",
    "fork",
    "review",
    "doctor",
    "apply",
    "update",
    "completion",
    "debug-models",
    "debug-app-server-send-message-v2",
    "debug-prompt-input",
    "cloud-list",
    "cloud-status",
    "cloud-diff",
    "cloud-exec",
    "cloud-apply",
    "sandbox-linux",
    "sandbox-macos",
    "sandbox-windows",
    "exec-server-start",
    "mcp-server",
    "app-open",
    "app-server-start",
    "app-server-proxy",
    "app-server-generate-ts",
    "app-server-generate-json-schema",
    "login-status",
    "login-api-key",
    "login-access-token",
    "login-device-auth",
    "logout",
    "mcp-list",
    "mcp-get",
    "mcp-add",
    "mcp-remove",
    "mcp-login",
    "mcp-logout",
    "plugin-list",
    "plugin-add",
    "plugin-remove",
    "plugin-marketplace-list",
    "plugin-marketplace-add",
    "plugin-marketplace-remove",
    "plugin-marketplace-upgrade",
    "features-list",
    "features-enable",
    "features-disable",
    "app-daemon-version",
    "app-daemon-bootstrap",
    "app-daemon-start",
    "app-daemon-restart",
    "app-daemon-stop",
    "app-daemon-enable-remote",
    "app-daemon-disable-remote",
    "remote-start",
    "remote-stop",
    "help",
    "raw",
}

MODE_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "exec": {"scope": "run", "kind": "agent", "title": "Run Codex exec"},
    "exec-resume": {"scope": "run", "kind": "agent", "title": "Resume Codex exec session"},
    "resume": {"scope": "run", "kind": "interactive", "title": "Run Codex resume"},
    "fork": {"scope": "run", "kind": "interactive", "title": "Run Codex fork"},
    "review": {"scope": "run", "kind": "agent", "title": "Run Codex review"},
    "doctor": {"scope": "run", "kind": "diagnostic", "title": "Run Codex doctor"},
    "apply": {"scope": "admin", "kind": "mutation", "title": "Apply Codex task diff locally"},
    "update": {"scope": "admin", "kind": "mutation", "title": "Update Codex CLI"},
    "completion": {"scope": "run", "kind": "read", "title": "Generate Codex shell completion"},
    "debug-models": {"scope": "run", "kind": "read", "title": "Dump model catalog"},
    "debug-app-server-send-message-v2": {
        "scope": "run",
        "kind": "debug",
        "title": "Send debug app-server v2 message",
    },
    "debug-prompt-input": {"scope": "run", "kind": "read", "title": "Render prompt input"},
    "cloud-list": {"scope": "run", "kind": "cloud", "title": "List Codex Cloud tasks"},
    "cloud-status": {"scope": "run", "kind": "cloud", "title": "Show Codex Cloud task status"},
    "cloud-diff": {"scope": "run", "kind": "cloud", "title": "Show Codex Cloud task diff"},
    "cloud-exec": {"scope": "admin", "kind": "cloud", "title": "Submit Codex Cloud task"},
    "cloud-apply": {"scope": "admin", "kind": "cloud", "title": "Apply Codex Cloud task diff"},
    "sandbox-linux": {"scope": "admin", "kind": "sandbox", "title": "Run command in Codex Linux sandbox"},
    "sandbox-macos": {"scope": "admin", "kind": "sandbox", "title": "Run command in Codex macOS sandbox"},
    "sandbox-windows": {"scope": "admin", "kind": "sandbox", "title": "Run command in Codex Windows sandbox"},
    "exec-server-start": {"scope": "admin", "kind": "service", "title": "Start Codex exec-server"},
    "mcp-server": {"scope": "admin", "kind": "service", "title": "Start Codex MCP stdio server"},
    "app-open": {"scope": "admin", "kind": "control", "title": "Open Codex Desktop app"},
    "app-server-start": {"scope": "admin", "kind": "service", "title": "Start Codex app-server"},
    "app-server-proxy": {"scope": "admin", "kind": "service", "title": "Proxy to Codex app-server socket"},
    "app-server-generate-ts": {"scope": "admin", "kind": "codegen", "title": "Generate app-server TypeScript bindings"},
    "app-server-generate-json-schema": {"scope": "admin", "kind": "codegen", "title": "Generate app-server JSON Schema"},
    "login-status": {"scope": "run", "kind": "read", "title": "Show Codex login status"},
    "login-api-key": {"scope": "admin", "kind": "auth", "title": "Login with API key from stdin"},
    "login-access-token": {"scope": "admin", "kind": "auth", "title": "Login with access token from stdin"},
    "login-device-auth": {"scope": "admin", "kind": "auth", "title": "Start Codex device auth login"},
    "logout": {"scope": "admin", "kind": "auth", "title": "Remove Codex credentials"},
    "mcp-list": {"scope": "run", "kind": "read", "title": "List MCP servers"},
    "mcp-get": {"scope": "run", "kind": "read", "title": "Show MCP server"},
    "mcp-add": {"scope": "admin", "kind": "config", "title": "Add MCP server"},
    "mcp-remove": {"scope": "admin", "kind": "config", "title": "Remove MCP server"},
    "mcp-login": {"scope": "admin", "kind": "auth", "title": "Authenticate MCP server"},
    "mcp-logout": {"scope": "admin", "kind": "auth", "title": "Deauthenticate MCP server"},
    "plugin-list": {"scope": "run", "kind": "read", "title": "List Codex plugins"},
    "plugin-add": {"scope": "admin", "kind": "config", "title": "Install Codex plugin"},
    "plugin-remove": {"scope": "admin", "kind": "config", "title": "Remove Codex plugin"},
    "plugin-marketplace-list": {"scope": "run", "kind": "read", "title": "List plugin marketplaces"},
    "plugin-marketplace-add": {"scope": "admin", "kind": "config", "title": "Add plugin marketplace"},
    "plugin-marketplace-remove": {"scope": "admin", "kind": "config", "title": "Remove plugin marketplace"},
    "plugin-marketplace-upgrade": {"scope": "admin", "kind": "config", "title": "Upgrade plugin marketplace"},
    "features-list": {"scope": "run", "kind": "read", "title": "List Codex features"},
    "features-enable": {"scope": "admin", "kind": "config", "title": "Enable Codex feature"},
    "features-disable": {"scope": "admin", "kind": "config", "title": "Disable Codex feature"},
    "app-daemon-version": {"scope": "run", "kind": "read", "title": "Show app-server daemon version"},
    "app-daemon-bootstrap": {"scope": "admin", "kind": "control", "title": "Bootstrap app-server daemon"},
    "app-daemon-start": {"scope": "admin", "kind": "control", "title": "Start app-server daemon"},
    "app-daemon-restart": {"scope": "admin", "kind": "control", "title": "Restart app-server daemon"},
    "app-daemon-stop": {"scope": "admin", "kind": "control", "title": "Stop app-server daemon"},
    "app-daemon-enable-remote": {"scope": "admin", "kind": "control", "title": "Enable app-server remote control"},
    "app-daemon-disable-remote": {"scope": "admin", "kind": "control", "title": "Disable app-server remote control"},
    "remote-start": {"scope": "admin", "kind": "control", "title": "Start remote-control daemon"},
    "remote-stop": {"scope": "admin", "kind": "control", "title": "Stop remote-control daemon"},
    "help": {"scope": "run", "kind": "read", "title": "Run whitelisted Codex help"},
    "raw": {"scope": "admin", "kind": "danger", "title": "Run raw Codex args"},
}

HELP_TOPICS = {
    "codex": [],
    "exec": ["exec", "--help"],
    "exec-resume": ["exec", "resume", "--help"],
    "review": ["review", "--help"],
    "doctor": ["doctor", "--help"],
    "apply": ["apply", "--help"],
    "update": ["update", "--help"],
    "completion": ["completion", "--help"],
    "debug": ["debug", "--help"],
    "debug-app-server": ["debug", "app-server", "--help"],
    "cloud": ["cloud", "--help"],
    "sandbox": ["sandbox", "--help"],
    "exec-server": ["exec-server", "--help"],
    "mcp-server": ["mcp-server", "--help"],
    "app": ["app", "--help"],
    "login": ["login", "--help"],
    "mcp": ["mcp", "--help"],
    "plugin": ["plugin", "--help"],
    "features": ["features", "--help"],
    "app-server": ["app-server", "--help"],
    "app-server-proxy": ["app-server", "proxy", "--help"],
    "app-daemon": ["app-server", "daemon", "--help"],
    "remote-control": ["remote-control", "--help"],
}

ADMIN_MODES = {mode for mode, details in MODE_DESCRIPTIONS.items() if details["scope"] == "admin"}


def split_command(command: str) -> list[str]:
    parts = shlex.split(command, posix=os.name != "nt") if command.strip() else ["codex"]
    if os.name == "nt" and parts:
        parts = resolve_windows_command(parts)
    return parts


def resolve_windows_command(parts: list[str]) -> list[str]:
    first = parts[0]
    suffix = Path(first).suffix.lower()
    if suffix in {".exe", ".cmd", ".bat"}:
        return parts
    if suffix == ".ps1":
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", first, *parts[1:]]
    for extension in (".cmd", ".exe", ".bat"):
        resolved = shutil.which(first + extension)
        if resolved:
            return [resolved, *parts[1:]]
    resolved = shutil.which(first)
    if resolved and Path(resolved).suffix.lower() == ".ps1":
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", resolved, *parts[1:]]
    if resolved:
        return [resolved, *parts[1:]]
    return parts


def toml_literal(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def codex_version(command: str = "codex") -> str:
    try:
        completed = subprocess.run(
            [*split_command(command), "--version"],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except OSError as exc:
        return f"unavailable: {exc}"
    output = (completed.stdout or completed.stderr or "").strip()
    return output or f"exit {completed.returncode}"


class CodexCommandBuilder:
    def __init__(self, config: BridgeConfig):
        self.config = config

    def build(self, workspace: WorkspaceConfig, mode: str, payload: dict[str, Any]) -> tuple[list[str], str]:
        normalized_mode = str(mode or "exec").strip().lower()
        if normalized_mode not in ALLOWED_MODES:
            raise ValueError(f"Unsupported Codex job mode: {mode}")
        if normalized_mode == "exec":
            return self._exec(workspace, payload)
        if normalized_mode == "exec-resume":
            return self._exec_resume(workspace, payload)
        if normalized_mode in {"resume", "fork"}:
            return self._interactive_session(normalized_mode, workspace, payload)
        if normalized_mode == "review":
            return self._review(workspace, payload)
        if normalized_mode == "doctor":
            return self._doctor(payload)
        if normalized_mode in {"apply", "update", "completion"}:
            return self._top_level(normalized_mode, workspace, payload)
        if normalized_mode.startswith("debug-"):
            return self._debug(normalized_mode, workspace, payload)
        if normalized_mode.startswith("cloud-"):
            return self._cloud(normalized_mode, workspace, payload)
        if normalized_mode.startswith("sandbox-"):
            return self._sandbox(normalized_mode, workspace, payload)
        if normalized_mode == "exec-server-start":
            return self._exec_server(payload)
        if normalized_mode == "mcp-server":
            return self._mcp_server(payload)
        if normalized_mode == "app-open":
            return self._app_open(workspace, payload)
        if normalized_mode == "app-server-start":
            return self._app_server_start(payload)
        if normalized_mode == "app-server-proxy":
            return self._app_server_proxy(payload)
        if normalized_mode.startswith("app-server-generate-"):
            return self._app_server_generate(normalized_mode, payload)
        if normalized_mode.startswith("login-") or normalized_mode == "logout":
            return self._login(normalized_mode, payload)
        if normalized_mode == "mcp-list":
            return self._mcp_list(payload)
        if normalized_mode == "mcp-get":
            return self._mcp_get(payload)
        if normalized_mode.startswith("mcp-"):
            return self._mcp_mutation(normalized_mode, payload)
        if normalized_mode == "plugin-list":
            return self._plugin_list(payload)
        if normalized_mode.startswith("plugin-marketplace-"):
            return self._plugin_marketplace(normalized_mode, payload)
        if normalized_mode.startswith("plugin-"):
            return self._plugin_mutation(normalized_mode, payload)
        if normalized_mode == "features-list":
            return self._features_list(payload)
        if normalized_mode.startswith("features-"):
            return self._features_mutation(normalized_mode, payload)
        if normalized_mode.startswith("app-daemon-"):
            return self._app_daemon(normalized_mode, payload)
        if normalized_mode == "remote-start":
            return [*split_command(self.config.codex_command), "remote-control", "start", "--json"], ""
        if normalized_mode == "remote-stop":
            return [*split_command(self.config.codex_command), "remote-control", "stop", "--json"], ""
        if normalized_mode == "help":
            return self._help(payload)
        return self._raw(payload)

    def _with_common_config(self, command: list[str], payload: dict[str, Any]) -> list[str]:
        extra_config = dict(self.config.codex_defaults().get("extra_config") or {})
        extra_config.update(dict(payload.get("extra_config") or {}))
        for key, value in sorted(extra_config.items()):
            if not key:
                continue
            command.extend(["-c", f"{key}={toml_literal(value)}"])
        return command

    def _append_images(self, command: list[str], workspace: WorkspaceConfig, payload: dict[str, Any]) -> None:
        for image in payload.get("images") or []:
            resolved = self._resolve_workspace_path(workspace, str(image))
            if not resolved.exists():
                raise ValueError(f"Image file does not exist: {resolved}")
            command.extend(["--image", str(resolved)])

    def _resolve_workspace_path(self, workspace: WorkspaceConfig, value: str) -> Path:
        raw = Path(value)
        resolved = raw.resolve() if raw.is_absolute() else (workspace.path / raw).resolve()
        allowed_roots = (workspace.path.resolve(), *workspace.allowed_additional_dirs)
        if not any(root == resolved or root in resolved.parents for root in allowed_roots):
            raise ValueError(f"Path is outside this workspace allowlist: {resolved}")
        return resolved

    def _append_interactive_common(self, command: list[str], workspace: WorkspaceConfig, payload: dict[str, Any]) -> None:
        sandbox = str(payload.get("sandbox") or workspace.default_sandbox or "workspace-write")
        approval = str(payload.get("approval_policy") or workspace.approval_policy or "never")
        if sandbox not in ALLOWED_SANDBOXES:
            raise ValueError(f"Unsupported sandbox: {sandbox}")
        if sandbox == "danger-full-access" and not self.config.allow_danger_full_access:
            raise ValueError("danger-full-access is disabled by bridge security config.")
        if approval not in ALLOWED_APPROVALS:
            raise ValueError(f"Unsupported approval policy: {approval}")
        command.extend(["--cd", str(workspace.path), "--sandbox", sandbox, "--ask-for-approval", approval])
        model = str(payload.get("model") or workspace.default_model or "")
        profile = str(payload.get("profile") or workspace.default_profile or "")
        profile_v2 = str(payload.get("profile_v2") or workspace.default_profile_v2 or "")
        if model:
            command.extend(["--model", model])
        if profile:
            command.extend(["--profile", profile])
        if profile_v2:
            command.extend(["--profile-v2", profile_v2])
        if bool(payload.get("search", self.config.codex_defaults().get("search_enabled", False))):
            command.append("--search")
        if bool(payload.get("no_alt_screen", True)):
            command.append("--no-alt-screen")
        self._append_images(command, workspace, payload)
        self._with_common_config(command, payload)

    def _exec(self, workspace: WorkspaceConfig, payload: dict[str, Any]) -> tuple[list[str], str]:
        prompt = str(payload.get("prompt") or "")
        if not prompt.strip():
            raise ValueError("Prompt is required for exec jobs.")

        sandbox = str(payload.get("sandbox") or workspace.default_sandbox or "workspace-write")
        approval = str(payload.get("approval_policy") or workspace.approval_policy or "never")
        if sandbox not in ALLOWED_SANDBOXES:
            raise ValueError(f"Unsupported sandbox: {sandbox}")
        if sandbox == "danger-full-access" and not self.config.allow_danger_full_access:
            raise ValueError("danger-full-access is disabled by bridge security config.")
        if approval not in ALLOWED_APPROVALS:
            raise ValueError(f"Unsupported approval policy: {approval}")

        command = [*split_command(self.config.codex_command), "exec", "--json", "--color", "never"]
        command.extend(["--cd", str(workspace.path)])
        command.extend(["--sandbox", sandbox])
        command.extend(["--ask-for-approval", approval])

        model = str(payload.get("model") or workspace.default_model or "")
        profile = str(payload.get("profile") or workspace.default_profile or "")
        profile_v2 = str(payload.get("profile_v2") or workspace.default_profile_v2 or "")
        if model:
            command.extend(["--model", model])
        if profile:
            command.extend(["--profile", profile])
        if profile_v2:
            command.extend(["--profile-v2", profile_v2])
        if bool(payload.get("search", self.config.codex_defaults().get("search_enabled", False))):
            command.append("--search")
        self._append_images(command, workspace, payload)

        for extra_dir in payload.get("add_dirs") or []:
            resolved = Path(extra_dir).resolve() if Path(str(extra_dir)).is_absolute() else (workspace.path / str(extra_dir)).resolve()
            if resolved not in workspace.allowed_additional_dirs:
                raise ValueError(f"Additional dir is not allowlisted for this workspace: {resolved}")
            command.extend(["--add-dir", str(resolved)])

        if bool(payload.get("ephemeral", False)):
            command.append("--ephemeral")
        if bool(payload.get("skip_git_repo_check", False)):
            command.append("--skip-git-repo-check")

        self._with_common_config(command, payload)
        command.append("-")
        return command, prompt

    def _interactive_session(self, mode: str, workspace: WorkspaceConfig, payload: dict[str, Any]) -> tuple[list[str], str]:
        command = [*split_command(self.config.codex_command), mode]
        if bool(payload.get("last", False)):
            command.append("--last")
        session_id = str(payload.get("session_id") or "").strip()
        if session_id:
            command.append(session_id)
        if bool(payload.get("all", False)):
            command.append("--all")
        if mode == "resume" and bool(payload.get("include_non_interactive", False)):
            command.append("--include-non-interactive")
        self._append_interactive_common(command, workspace, payload)
        prompt = str(payload.get("prompt") or "")
        if prompt.strip():
            command.append(prompt)
        return command, ""

    def _exec_resume(self, workspace: WorkspaceConfig, payload: dict[str, Any]) -> tuple[list[str], str]:
        prompt = str(payload.get("prompt") or "")
        command = [*split_command(self.config.codex_command), "exec", "resume", "--json"]

        model = str(payload.get("model") or workspace.default_model or "")
        if model:
            command.extend(["--model", model])
        if bool(payload.get("last", False)):
            command.append("--last")
        session_id = str(payload.get("session_id") or "").strip()
        if session_id:
            command.append(session_id)
        elif not bool(payload.get("last", False)):
            raise ValueError("session_id or last=true is required for exec-resume.")
        if bool(payload.get("all", False)):
            command.append("--all")
        if bool(payload.get("ephemeral", False)):
            command.append("--ephemeral")
        if bool(payload.get("skip_git_repo_check", False)):
            command.append("--skip-git-repo-check")
        self._append_images(command, workspace, payload)
        self._with_common_config(command, payload)
        if prompt.strip():
            command.append("-")
        return command, prompt

    def _review(self, workspace: WorkspaceConfig, payload: dict[str, Any]) -> tuple[list[str], str]:
        command = [*split_command(self.config.codex_command), "review"]
        prompt = str(payload.get("prompt") or "")
        if bool(payload.get("uncommitted", True)):
            command.append("--uncommitted")
        if payload.get("base"):
            command.extend(["--base", str(payload["base"])])
        if payload.get("commit"):
            command.extend(["--commit", str(payload["commit"])])
        if payload.get("title"):
            command.extend(["--title", str(payload["title"])])
        self._with_common_config(command, payload)
        if prompt.strip():
            command.append("-")
        return command, prompt

    def _doctor(self, payload: dict[str, Any]) -> tuple[list[str], str]:
        command = [*split_command(self.config.codex_command), "doctor", "--json"]
        if bool(payload.get("summary", False)):
            command.append("--summary")
        return command, ""

    def _top_level(self, mode: str, workspace: WorkspaceConfig, payload: dict[str, Any]) -> tuple[list[str], str]:
        if mode == "apply":
            command = [*split_command(self.config.codex_command), "apply", self._required_text(payload, "task_id")]
        elif mode == "update":
            command = [*split_command(self.config.codex_command), "update"]
        elif mode == "completion":
            shell = str(payload.get("shell") or "powershell").strip()
            if shell not in {"bash", "elvish", "fish", "powershell", "zsh"}:
                raise ValueError(f"Unsupported completion shell: {shell}")
            command = [*split_command(self.config.codex_command), "completion", shell]
        else:
            raise ValueError(f"Unsupported top-level mode: {mode}")
        self._with_common_config(command, payload)
        return command, ""

    def _debug(self, mode: str, workspace: WorkspaceConfig, payload: dict[str, Any]) -> tuple[list[str], str]:
        if mode == "debug-models":
            command = [*split_command(self.config.codex_command), "debug", "models"]
            if bool(payload.get("bundled", True)):
                command.append("--bundled")
        elif mode == "debug-app-server-send-message-v2":
            message = str(payload.get("message") or payload.get("prompt") or "").strip()
            if not message:
                raise ValueError("message or prompt is required for debug-app-server-send-message-v2.")
            command = [*split_command(self.config.codex_command), "debug", "app-server", "send-message-v2", message]
        elif mode == "debug-prompt-input":
            command = [*split_command(self.config.codex_command), "debug", "prompt-input"]
            prompt = str(payload.get("prompt") or "")
            if prompt.strip():
                command.append(prompt)
            self._append_images(command, workspace, payload)
        else:
            raise ValueError(f"Unsupported debug mode: {mode}")
        self._with_common_config(command, payload)
        return command, ""

    def _cloud(self, mode: str, workspace: WorkspaceConfig, payload: dict[str, Any]) -> tuple[list[str], str]:
        if mode == "cloud-list":
            command = [*split_command(self.config.codex_command), "cloud", "list", "--json"]
            env_id = str(payload.get("env_id") or "").strip()
            if env_id:
                command.extend(["--env", env_id])
            if payload.get("limit"):
                command.extend(["--limit", str(payload["limit"])])
            if payload.get("cursor"):
                command.extend(["--cursor", str(payload["cursor"])])
        elif mode == "cloud-status":
            command = [*split_command(self.config.codex_command), "cloud", "status", self._required_text(payload, "task_id")]
        elif mode == "cloud-diff":
            command = [*split_command(self.config.codex_command), "cloud", "diff", self._required_text(payload, "task_id")]
            if payload.get("attempt"):
                command.extend(["--attempt", str(payload["attempt"])])
        elif mode == "cloud-apply":
            command = [*split_command(self.config.codex_command), "cloud", "apply", self._required_text(payload, "task_id")]
            if payload.get("attempt"):
                command.extend(["--attempt", str(payload["attempt"])])
        elif mode == "cloud-exec":
            command = [
                *split_command(self.config.codex_command),
                "cloud",
                "exec",
                "--env",
                self._required_text(payload, "env_id"),
            ]
            if payload.get("attempts"):
                command.extend(["--attempts", str(payload["attempts"])])
            branch = str(payload.get("branch") or "").strip()
            if branch:
                command.extend(["--branch", branch])
            prompt = str(payload.get("prompt") or "")
            if prompt.strip():
                command.append(prompt)
        else:
            raise ValueError(f"Unsupported cloud mode: {mode}")
        self._with_common_config(command, payload)
        return command, ""

    def _sandbox(self, mode: str, workspace: WorkspaceConfig, payload: dict[str, Any]) -> tuple[list[str], str]:
        platform = mode.rsplit("-", 1)[-1]
        command_args = payload.get("command") or []
        if not isinstance(command_args, list) or not all(isinstance(item, str) for item in command_args):
            raise ValueError(f"command must be a string array for {mode}.")
        if not command_args:
            raise ValueError(f"command is required for {mode}.")
        command = [*split_command(self.config.codex_command), "sandbox", platform, "--cd", str(workspace.path)]
        profile = str(payload.get("permissions_profile") or "").strip()
        if profile:
            command.extend(["--permissions-profile", profile])
        if bool(payload.get("include_managed_config", False)):
            command.append("--include-managed-config")
        if platform == "macos":
            sockets = payload.get("allow_unix_sockets") or []
            if isinstance(sockets, str):
                sockets = [sockets]
            if not isinstance(sockets, list) or not all(isinstance(item, str) for item in sockets):
                raise ValueError("allow_unix_sockets must be a string or string array.")
            for socket_path in sockets:
                if socket_path.strip():
                    command.extend(["--allow-unix-socket", socket_path.strip()])
            if bool(payload.get("log_denials", False)):
                command.append("--log-denials")
        self._with_common_config(command, payload)
        command.extend(command_args)
        return command, ""

    def _exec_server(self, payload: dict[str, Any]) -> tuple[list[str], str]:
        command = [*split_command(self.config.codex_command), "exec-server"]
        listen = str(payload.get("listen") or "ws://127.0.0.1:0").strip()
        command.extend(["--listen", listen])
        remote = str(payload.get("remote") or "").strip()
        if remote:
            command.extend(["--remote", remote])
        environment_id = str(payload.get("environment_id") or "").strip()
        if environment_id:
            command.extend(["--environment-id", environment_id])
        name = str(payload.get("name") or "").strip()
        if name:
            command.extend(["--name", name])
        if bool(payload.get("use_agent_identity_auth", False)):
            command.append("--use-agent-identity-auth")
        self._with_common_config(command, payload)
        return command, ""

    def _mcp_server(self, payload: dict[str, Any]) -> tuple[list[str], str]:
        command = [*split_command(self.config.codex_command), "mcp-server"]
        self._with_common_config(command, payload)
        return command, ""

    def _app_open(self, workspace: WorkspaceConfig, payload: dict[str, Any]) -> tuple[list[str], str]:
        command = [*split_command(self.config.codex_command), "app"]
        download_url = str(payload.get("download_url") or "").strip()
        if download_url:
            command.extend(["--download-url", download_url])
        self._with_common_config(command, payload)
        path = str(payload.get("path") or workspace.path).strip()
        if path:
            command.append(path)
        return command, ""

    def _append_app_server_auth(self, command: list[str], payload: dict[str, Any]) -> None:
        ws_auth = str(payload.get("ws_auth") or "").strip()
        if ws_auth:
            if ws_auth not in {"capability-token", "signed-bearer-token"}:
                raise ValueError(f"Unsupported app-server ws_auth mode: {ws_auth}")
            command.extend(["--ws-auth", ws_auth])
        for payload_key, flag in (
            ("ws_token_file", "--ws-token-file"),
            ("ws_token_sha256", "--ws-token-sha256"),
            ("ws_shared_secret_file", "--ws-shared-secret-file"),
            ("ws_issuer", "--ws-issuer"),
            ("ws_audience", "--ws-audience"),
            ("ws_max_clock_skew_seconds", "--ws-max-clock-skew-seconds"),
        ):
            value = str(payload.get(payload_key) or "").strip()
            if value:
                command.extend([flag, value])

    def _app_server_start(self, payload: dict[str, Any]) -> tuple[list[str], str]:
        command = [*split_command(self.config.codex_command), "app-server"]
        listen = str(payload.get("listen") or "stdio://").strip()
        if listen:
            command.extend(["--listen", listen])
        if bool(payload.get("analytics_default_enabled", False)):
            command.append("--analytics-default-enabled")
        self._append_app_server_auth(command, payload)
        self._with_common_config(command, payload)
        return command, ""

    def _app_server_proxy(self, payload: dict[str, Any]) -> tuple[list[str], str]:
        command = [*split_command(self.config.codex_command), "app-server", "proxy"]
        sock = str(payload.get("sock") or "").strip()
        if sock:
            command.extend(["--sock", sock])
        self._with_common_config(command, payload)
        return command, ""

    def _app_server_generate(self, mode: str, payload: dict[str, Any]) -> tuple[list[str], str]:
        out_dir = self._required_text(payload, "out_dir")
        subcommand = "generate-ts" if mode == "app-server-generate-ts" else "generate-json-schema"
        command = [*split_command(self.config.codex_command), "app-server", subcommand, "--out", out_dir]
        if mode == "app-server-generate-ts":
            prettier = str(payload.get("prettier") or "").strip()
            if prettier:
                command.extend(["--prettier", prettier])
        if bool(payload.get("experimental", False)):
            command.append("--experimental")
        self._with_common_config(command, payload)
        return command, ""

    def _required_text(self, payload: dict[str, Any], key: str) -> str:
        value = str(payload.get(key) or "").strip()
        if not value:
            raise ValueError(f"{key} is required.")
        return value

    def _login(self, mode: str, payload: dict[str, Any]) -> tuple[list[str], str]:
        if mode == "login-status":
            command = [*split_command(self.config.codex_command), "login", "status"]
            self._with_common_config(command, payload)
            return command, ""
        if mode == "login-api-key":
            secret = self._required_text(payload, "secret")
            command = [*split_command(self.config.codex_command), "login", "--with-api-key"]
            self._with_common_config(command, payload)
            return command, secret
        if mode == "login-access-token":
            secret = self._required_text(payload, "secret")
            command = [*split_command(self.config.codex_command), "login", "--with-access-token"]
            self._with_common_config(command, payload)
            return command, secret
        if mode == "login-device-auth":
            command = [*split_command(self.config.codex_command), "login", "--device-auth"]
            self._with_common_config(command, payload)
            return command, ""
        if mode == "logout":
            command = [*split_command(self.config.codex_command), "logout"]
            self._with_common_config(command, payload)
            return command, ""
        raise ValueError(f"Unsupported login mode: {mode}")

    def _mcp_list(self, payload: dict[str, Any]) -> tuple[list[str], str]:
        command = [*split_command(self.config.codex_command), "mcp", "list", "--json"]
        self._with_common_config(command, payload)
        return command, ""

    def _mcp_get(self, payload: dict[str, Any]) -> tuple[list[str], str]:
        name = self._required_text(payload, "name")
        command = [*split_command(self.config.codex_command), "mcp", "get", "--json", name]
        self._with_common_config(command, payload)
        return command, ""

    def _mcp_mutation(self, mode: str, payload: dict[str, Any]) -> tuple[list[str], str]:
        if mode == "mcp-add":
            name = self._required_text(payload, "name")
            command = [*split_command(self.config.codex_command), "mcp", "add", name]
            env = dict(payload.get("env") or {})
            for key, value in sorted(env.items()):
                if not key:
                    continue
                command.extend(["--env", f"{key}={value}"])
            url = str(payload.get("url") or "").strip()
            launch_command = payload.get("command") or []
            if url:
                command.extend(["--url", url])
                bearer_env = str(payload.get("bearer_token_env_var") or "").strip()
                if bearer_env:
                    command.extend(["--bearer-token-env-var", bearer_env])
            else:
                if not isinstance(launch_command, list) or not all(isinstance(item, str) for item in launch_command):
                    raise ValueError("command must be a string array for stdio mcp-add.")
                if not launch_command:
                    raise ValueError("url or command is required for mcp-add.")
                command.append("--")
                command.extend(launch_command)
            self._with_common_config(command, payload)
            return command, ""
        if mode == "mcp-remove":
            command = [*split_command(self.config.codex_command), "mcp", "remove", self._required_text(payload, "name")]
            self._with_common_config(command, payload)
            return command, ""
        if mode == "mcp-login":
            command = [*split_command(self.config.codex_command), "mcp", "login", self._required_text(payload, "name")]
            scopes = str(payload.get("scopes") or "").strip()
            if scopes:
                command.extend(["--scopes", scopes])
            self._with_common_config(command, payload)
            return command, ""
        if mode == "mcp-logout":
            command = [*split_command(self.config.codex_command), "mcp", "logout", self._required_text(payload, "name")]
            self._with_common_config(command, payload)
            return command, ""
        raise ValueError(f"Unsupported MCP mode: {mode}")

    def _plugin_list(self, payload: dict[str, Any]) -> tuple[list[str], str]:
        command = [*split_command(self.config.codex_command), "plugin", "list"]
        marketplace = str(payload.get("marketplace") or "").strip()
        if marketplace:
            command.extend(["--marketplace", marketplace])
        self._with_common_config(command, payload)
        return command, ""

    def _plugin_mutation(self, mode: str, payload: dict[str, Any]) -> tuple[list[str], str]:
        subcommand = {"plugin-add": "add", "plugin-remove": "remove"}.get(mode)
        if subcommand is None:
            raise ValueError(f"Unsupported plugin mode: {mode}")
        plugin = self._required_text(payload, "plugin")
        command = [*split_command(self.config.codex_command), "plugin", subcommand, plugin]
        marketplace = str(payload.get("marketplace") or "").strip()
        if marketplace:
            command.extend(["--marketplace", marketplace])
        self._with_common_config(command, payload)
        return command, ""

    def _plugin_marketplace(self, mode: str, payload: dict[str, Any]) -> tuple[list[str], str]:
        if mode == "plugin-marketplace-list":
            command = [*split_command(self.config.codex_command), "plugin", "marketplace", "list"]
            self._with_common_config(command, payload)
            return command, ""
        if mode == "plugin-marketplace-add":
            command = [
                *split_command(self.config.codex_command),
                "plugin",
                "marketplace",
                "add",
                self._required_text(payload, "source"),
            ]
            ref = str(payload.get("ref") or "").strip()
            if ref:
                command.extend(["--ref", ref])
            sparse = payload.get("sparse") or []
            if isinstance(sparse, str):
                sparse = [sparse]
            if not isinstance(sparse, list) or not all(isinstance(item, str) for item in sparse):
                raise ValueError("sparse must be a string or string array.")
            for path in sparse:
                if path.strip():
                    command.extend(["--sparse", path.strip()])
            self._with_common_config(command, payload)
            return command, ""
        if mode == "plugin-marketplace-remove":
            command = [
                *split_command(self.config.codex_command),
                "plugin",
                "marketplace",
                "remove",
                self._required_text(payload, "marketplace"),
            ]
            self._with_common_config(command, payload)
            return command, ""
        if mode == "plugin-marketplace-upgrade":
            command = [*split_command(self.config.codex_command), "plugin", "marketplace", "upgrade"]
            marketplace = str(payload.get("marketplace") or "").strip()
            if marketplace:
                command.append(marketplace)
            self._with_common_config(command, payload)
            return command, ""
        raise ValueError(f"Unsupported plugin marketplace mode: {mode}")

    def _features_list(self, payload: dict[str, Any]) -> tuple[list[str], str]:
        command = [*split_command(self.config.codex_command), "features", "list"]
        self._with_common_config(command, payload)
        return command, ""

    def _features_mutation(self, mode: str, payload: dict[str, Any]) -> tuple[list[str], str]:
        subcommand = {"features-enable": "enable", "features-disable": "disable"}.get(mode)
        if subcommand is None:
            raise ValueError(f"Unsupported features mode: {mode}")
        command = [*split_command(self.config.codex_command), "features", subcommand, self._required_text(payload, "feature")]
        self._with_common_config(command, payload)
        return command, ""

    def _app_daemon(self, mode: str, payload: dict[str, Any]) -> tuple[list[str], str]:
        command_map = {
            "app-daemon-version": "version",
            "app-daemon-bootstrap": "bootstrap",
            "app-daemon-start": "start",
            "app-daemon-restart": "restart",
            "app-daemon-stop": "stop",
            "app-daemon-enable-remote": "enable-remote-control",
            "app-daemon-disable-remote": "disable-remote-control",
        }
        command = [*split_command(self.config.codex_command), "app-server", "daemon", command_map[mode]]
        if mode == "app-daemon-bootstrap" and bool(payload.get("remote_control", False)):
            command.append("--remote-control")
        self._with_common_config(command, payload)
        return command, ""

    def _help(self, payload: dict[str, Any]) -> tuple[list[str], str]:
        topic = str(payload.get("topic") or "codex").strip().lower()
        if topic not in HELP_TOPICS:
            raise ValueError(f"Unsupported help topic: {topic}")
        args = HELP_TOPICS[topic] or ["--help"]
        return [*split_command(self.config.codex_command), *args], ""

    def _raw(self, payload: dict[str, Any]) -> tuple[list[str], str]:
        if not self.config.allow_raw_codex_args:
            raise ValueError("Raw Codex args are disabled by bridge security config.")
        args = payload.get("args") or []
        if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
            raise ValueError("Raw Codex args must be a string array.")
        stdin = str(payload.get("stdin") or "")
        return [*split_command(self.config.codex_command), *args], stdin
