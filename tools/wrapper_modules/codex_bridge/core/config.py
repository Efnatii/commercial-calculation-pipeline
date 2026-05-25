from __future__ import annotations

import copy
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONFIG_VERSION = 1
ALLOWED_SCOPES = {"read", "run", "admin"}

DEFAULT_CONFIG: dict[str, Any] = {
    "version": CONFIG_VERSION,
    "server": {
        "host": "127.0.0.1",
        "port": 8765,
        "public_base_url": "http://127.0.0.1:8765",
        "allowed_origins": [
            "http://127.0.0.1:8765",
            "http://localhost:8765",
            "https://localhost",
        ],
        "allowed_origin_patterns": [
            "https://*.github.io",
        ],
        "enable_private_network_cors": True,
        "tls": {
            "enabled": False,
            "cert_file": "",
            "key_file": "",
        },
    },
    "runtime": {
        "state_dir": ".codex-bridge",
        "static_dir": "docs/codex-ui",
        "codex_command": "codex",
        "default_timeout_seconds": 3600,
        "max_concurrent_jobs": 2,
    },
    "codex": {
        "default_model": "",
        "default_profile": "",
        "default_profile_v2": "",
        "default_sandbox": "workspace-write",
        "default_approval_policy": "never",
        "search_enabled": False,
        "extra_config": {},
    },
    "security": {
        "require_api_tokens": True,
        "allow_loopback_without_token": True,
        "allow_loopback_admin_without_token": True,
        "allow_lan_without_token": False,
        "allow_lan_static_ui": False,
        "allow_lan_health": False,
        "no_auth_scopes": [],
        "allow_danger_full_access": False,
        "allow_raw_codex_args": False,
    },
    "workspaces": [
        {
            "id": "main",
            "name": "Текущий репозиторий",
            "path": ".",
            "codex_home": ".codex-bridge/workspaces/main/codex-home",
            "default_model": "",
            "default_profile": "",
            "default_profile_v2": "",
            "default_sandbox": "workspace-write",
            "approval_policy": "never",
            "allowed_additional_dirs": [],
            "env": {},
            "owner": "",
            "enabled": True,
        }
    ],
}


_ID_RE = re.compile(r"[^a-z0-9_.-]+")


def sanitize_id(value: str) -> str:
    normalized = _ID_RE.sub("-", value.strip().lower()).strip(".-_")
    return normalized or "item"


def discover_repo_root(start: Path | None = None) -> Path:
    env_root = os.environ.get("CODEX_BRIDGE_REPO_ROOT")
    candidates: list[Path] = []
    if env_root:
        candidates.append(Path(env_root))
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent)
    candidates.append((start or Path.cwd()).resolve())

    for initial in candidates:
        current = initial.resolve()
        probe = current if current.is_dir() else current.parent
        for candidate in (probe, *probe.parents):
            if (candidate / "tools" / "wrapper.py").exists() and (candidate / "README.md").exists():
                return candidate
            if (candidate / "configs").is_dir() and (candidate / "docs").is_dir():
                return candidate
    return (start or Path.cwd()).resolve()


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as fh:
        loaded = json.load(fh)
    if not isinstance(loaded, dict):
        raise ValueError(f"Config root must be a JSON object: {path}")
    return loaded


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def resolve_path(value: str | os.PathLike[str], base: Path) -> Path:
    raw = Path(value)
    if raw.is_absolute():
        return raw.resolve()
    return (base / raw).resolve()


@dataclass(frozen=True)
class WorkspaceConfig:
    id: str
    name: str
    owner: str
    path: Path
    codex_home: Path
    default_model: str
    default_profile: str
    default_profile_v2: str
    default_sandbox: str
    approval_policy: str
    allowed_additional_dirs: tuple[Path, ...]
    env: dict[str, str]
    enabled: bool

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "owner": self.owner,
            "path": str(self.path),
            "codex_home": str(self.codex_home),
            "default_model": self.default_model,
            "default_profile": self.default_profile,
            "default_profile_v2": self.default_profile_v2,
            "default_sandbox": self.default_sandbox,
            "approval_policy": self.approval_policy,
            "allowed_additional_dirs": [str(path) for path in self.allowed_additional_dirs],
            "enabled": self.enabled,
        }


class BridgeConfig:
    def __init__(self, raw: dict[str, Any], repo_root: Path, config_path: Path | None = None):
        self.raw = raw
        self.repo_root = repo_root
        self.config_path = config_path

    @classmethod
    def load(cls, config_path: Path | None = None, repo_root: Path | None = None) -> "BridgeConfig":
        root = discover_repo_root(repo_root)
        if config_path is None:
            path = root / ".codex-bridge" / "server.json"
        else:
            path = resolve_path(config_path, root)
        raw = deep_merge(DEFAULT_CONFIG, read_json(path)) if path.exists() else copy.deepcopy(DEFAULT_CONFIG)
        return cls(raw, root, path)

    @property
    def server_host(self) -> str:
        return str(self.raw["server"].get("host") or "127.0.0.1")

    @property
    def server_port(self) -> int:
        return int(self.raw["server"].get("port") or 8765)

    @property
    def state_dir(self) -> Path:
        return resolve_path(str(self.raw["runtime"].get("state_dir") or ".codex-bridge"), self.repo_root)

    @property
    def static_dir(self) -> Path:
        configured = resolve_path(str(self.raw["runtime"].get("static_dir") or "docs/codex-ui"), self.repo_root)
        if configured.exists():
            return configured
        bundle_root = getattr(sys, "_MEIPASS", None)
        if bundle_root:
            bundled = Path(bundle_root) / "docs" / "codex-ui"
            if bundled.exists():
                return bundled.resolve()
        return configured

    @property
    def codex_command(self) -> str:
        return str(self.raw["runtime"].get("codex_command") or "codex")

    @property
    def max_concurrent_jobs(self) -> int:
        return max(1, int(self.raw["runtime"].get("max_concurrent_jobs") or 1))

    @property
    def default_timeout_seconds(self) -> int:
        return max(30, int(self.raw["runtime"].get("default_timeout_seconds") or 3600))

    @property
    def allowed_origins(self) -> tuple[str, ...]:
        origins = self.raw["server"].get("allowed_origins") or []
        return tuple(str(origin) for origin in origins)

    @property
    def allowed_origin_patterns(self) -> tuple[str, ...]:
        patterns = self.raw["server"].get("allowed_origin_patterns") or []
        return tuple(str(pattern) for pattern in patterns)

    @property
    def enable_private_network_cors(self) -> bool:
        return bool(self.raw["server"].get("enable_private_network_cors", True))

    @property
    def allow_danger_full_access(self) -> bool:
        return bool(self.raw["security"].get("allow_danger_full_access", False))

    @property
    def require_api_tokens(self) -> bool:
        return bool(self.raw["security"].get("require_api_tokens", True))

    @property
    def allow_loopback_without_token(self) -> bool:
        return bool(self.raw["security"].get("allow_loopback_without_token", True))

    @property
    def allow_loopback_admin_without_token(self) -> bool:
        return bool(self.raw["security"].get("allow_loopback_admin_without_token", True))

    @property
    def allow_lan_without_token(self) -> bool:
        return bool(self.raw["security"].get("allow_lan_without_token", False))

    @property
    def allow_lan_static_ui(self) -> bool:
        return bool(self.raw["security"].get("allow_lan_static_ui", False))

    @property
    def allow_lan_health(self) -> bool:
        return bool(self.raw["security"].get("allow_lan_health", False))

    @property
    def no_auth_scopes(self) -> tuple[str, ...]:
        configured = self.raw["security"].get("no_auth_scopes") or []
        scopes = tuple(str(scope) for scope in configured if str(scope) in ALLOWED_SCOPES)
        return scopes

    @property
    def allow_raw_codex_args(self) -> bool:
        return bool(self.raw["security"].get("allow_raw_codex_args", False))

    def tls_config(self) -> dict[str, Any]:
        return dict(self.raw["server"].get("tls") or {})

    def codex_defaults(self) -> dict[str, Any]:
        return dict(self.raw.get("codex") or {})

    def workspace_root(self, workspace_id: str) -> Path:
        return self.state_dir / "workspaces" / sanitize_id(workspace_id)

    def workspaces(self) -> tuple[WorkspaceConfig, ...]:
        result: list[WorkspaceConfig] = []
        for item in self.raw.get("workspaces") or []:
            if not isinstance(item, dict):
                continue
            workspace_id = sanitize_id(str(item.get("id") or item.get("name") or "workspace"))
            path = resolve_path(str(item.get("path") or "."), self.repo_root)
            codex_home_value = item.get("codex_home") or f".codex-bridge/workspaces/{workspace_id}/codex-home"
            codex_home = resolve_path(str(codex_home_value), self.repo_root)
            dirs = tuple(
                resolve_path(str(extra), self.repo_root)
                for extra in (item.get("allowed_additional_dirs") or [])
                if str(extra).strip()
            )
            env = {str(key): str(value) for key, value in dict(item.get("env") or {}).items()}
            result.append(
                WorkspaceConfig(
                    id=workspace_id,
                    name=str(item.get("name") or workspace_id),
                    owner=str(item.get("owner") or item.get("owner_user_name") or "").strip(),
                    path=path,
                    codex_home=codex_home,
                    default_model=str(item.get("default_model") or self.raw["codex"].get("default_model") or ""),
                    default_profile=str(item.get("default_profile") or self.raw["codex"].get("default_profile") or ""),
                    default_profile_v2=str(
                        item.get("default_profile_v2") or self.raw["codex"].get("default_profile_v2") or ""
                    ),
                    default_sandbox=str(
                        item.get("default_sandbox") or self.raw["codex"].get("default_sandbox") or "workspace-write"
                    ),
                    approval_policy=str(
                        item.get("approval_policy")
                        or self.raw["codex"].get("default_approval_policy")
                        or "never"
                    ),
                    allowed_additional_dirs=dirs,
                    env=env,
                    enabled=bool(item.get("enabled", True)),
                )
            )
        return tuple(result)

    def get_workspace(self, workspace_id: str | None) -> WorkspaceConfig | None:
        target = sanitize_id(workspace_id or "")
        for workspace in self.workspaces():
            if workspace.id == target and workspace.enabled:
                return workspace
        enabled = [workspace for workspace in self.workspaces() if workspace.enabled]
        return enabled[0] if workspace_id in (None, "") and enabled else None

    def ensure_runtime_dirs(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        (self.state_dir / "jobs").mkdir(parents=True, exist_ok=True)
        (self.state_dir / "workspaces").mkdir(parents=True, exist_ok=True)
        for workspace in self.workspaces():
            workspace.codex_home.mkdir(parents=True, exist_ok=True)

    def save(self) -> None:
        if self.config_path is None:
            raise ValueError("Cannot save config without a config path.")
        write_json(self.config_path, self.raw)

    def upsert_workspace(self, item: dict[str, Any]) -> WorkspaceConfig:
        workspace_id = sanitize_id(str(item.get("id") or item.get("name") or "workspace"))
        normalized = dict(item)
        normalized["id"] = workspace_id
        normalized.setdefault("name", workspace_id)
        normalized.setdefault("owner", "")
        normalized.setdefault("path", ".")
        normalized.setdefault("codex_home", f".codex-bridge/workspaces/{workspace_id}/codex-home")
        normalized.setdefault("enabled", True)

        workspaces = [entry for entry in self.raw.setdefault("workspaces", []) if isinstance(entry, dict)]
        for index, entry in enumerate(workspaces):
            if sanitize_id(str(entry.get("id") or "")) == workspace_id:
                workspaces[index] = normalized
                break
        else:
            workspaces.append(normalized)
        self.raw["workspaces"] = workspaces
        self.save()
        created = self.get_workspace(workspace_id)
        if created is None:
            raise ValueError(f"Workspace did not become available: {workspace_id}")
        created.codex_home.mkdir(parents=True, exist_ok=True)
        return created

    def remove_workspace(self, workspace_id: str) -> bool:
        target = sanitize_id(workspace_id)
        workspaces = [entry for entry in self.raw.get("workspaces", []) if isinstance(entry, dict)]
        updated = [entry for entry in workspaces if sanitize_id(str(entry.get("id") or "")) != target]
        changed = len(updated) != len(workspaces)
        if changed:
            self.raw["workspaces"] = updated
            self.save()
        return changed

    def public_dict(self) -> dict[str, Any]:
        return {
            "version": self.raw.get("version", CONFIG_VERSION),
            "repo_root": str(self.repo_root),
            "state_dir": str(self.state_dir),
            "static_dir": str(self.static_dir),
            "server": {
                "host": self.server_host,
                "port": self.server_port,
                "public_base_url": self.raw["server"].get("public_base_url", ""),
                "allowed_origins": list(self.allowed_origins),
                "allowed_origin_patterns": list(self.allowed_origin_patterns),
                "enable_private_network_cors": self.enable_private_network_cors,
                "tls_enabled": bool(self.tls_config().get("enabled", False)),
            },
            "runtime": {
                "codex_command": self.codex_command,
                "default_timeout_seconds": self.default_timeout_seconds,
                "max_concurrent_jobs": self.max_concurrent_jobs,
            },
            "security": {
                "require_api_tokens": self.require_api_tokens,
                "allow_loopback_without_token": self.allow_loopback_without_token,
                "allow_loopback_admin_without_token": self.allow_loopback_admin_without_token,
                "allow_lan_without_token": self.allow_lan_without_token,
                "allow_lan_static_ui": self.allow_lan_static_ui,
                "allow_lan_health": self.allow_lan_health,
                "no_auth_scopes": list(self.no_auth_scopes),
                "allow_danger_full_access": self.allow_danger_full_access,
                "allow_raw_codex_args": self.allow_raw_codex_args,
            },
        }


def initialize_config(target: Path, repo_root: Path | None = None, overwrite: bool = False) -> BridgeConfig:
    root = discover_repo_root(repo_root)
    path = resolve_path(target, root)
    if path.exists() and not overwrite:
        return BridgeConfig.load(path, root)
    raw = copy.deepcopy(DEFAULT_CONFIG)
    write_json(path, raw)
    return BridgeConfig.load(path, root)
