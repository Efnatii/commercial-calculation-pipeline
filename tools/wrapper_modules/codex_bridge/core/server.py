from __future__ import annotations

import json
import mimetypes
import fnmatch
import socket
import ssl
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from wrapper_modules.codex_bridge.core.auth import TokenRecord, TokenStore, iso_now
from wrapper_modules.codex_bridge.core.codex import ALLOWED_MODES, ADMIN_MODES, MODE_DESCRIPTIONS, codex_version
from wrapper_modules.codex_bridge.core.config import BridgeConfig, sanitize_id
from wrapper_modules.codex_bridge.core.jobs import JobManager, normalize_user_name


class BridgeHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], handler_class: type[BaseHTTPRequestHandler], config: BridgeConfig):
        super().__init__(server_address, handler_class)
        self.config = config
        self.tokens = TokenStore(config.state_dir / "tokens.json")
        self.jobs = JobManager(config)
        self.bootstrap_token = self.tokens.rotate_bootstrap_admin(config.state_dir / "bootstrap-admin-token.txt")
        self.codex_version = codex_version(config.codex_command)


class BridgeHandler(BaseHTTPRequestHandler):
    server: BridgeHTTPServer

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - inherited name.
        message = "%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args)
        print(message, end="")

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    def _dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            if path == "/health" and method == "GET":
                if not self._is_loopback_client() and not self.server.config.allow_lan_health:
                    raise PermissionError(
                        "Bridge health is disabled for LAN clients. Use authenticated /api/status instead."
                    )
                self._json(
                    {
                        "ok": True,
                        "service": "codex-bridge",
                        "codex_version": self.server.codex_version,
                        "time": int(time.time()),
                    }
                )
                return
            if path.startswith("/api/"):
                self._api(method, path, parse_qs(parsed.query))
                return
            self._static(path)
        except PermissionError as exc:
            self._json({"ok": False, "error": str(exc)}, HTTPStatus.FORBIDDEN)
        except ValueError as exc:
            self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except FileNotFoundError:
            self._json({"ok": False, "error": "Not found."}, HTTPStatus.NOT_FOUND)
        except Exception as exc:  # noqa: BLE001 - API must return structured failures.
            self._json({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _api(self, method: str, path: str, query: dict[str, list[str]]) -> None:
        if method == "GET" and path == "/api/local-user-token":
            if not self._is_loopback_client():
                raise PermissionError("Current machine token is only available from this computer.")
            record = self.server.tokens.authenticate(self.server.bootstrap_token)
            self._json(
                {
                    "ok": True,
                    "token": self.server.bootstrap_token,
                    "record": record.public_dict() if record else None,
                    "created": False,
                    "rotates_on_server_start": True,
                }
            )
            return

        token = self._authenticated()
        user_name = self._request_user_name(token)

        if method == "GET" and path == "/api/status":
            self.server.tokens.require(token, "read")
            self._json(
                {
                    "ok": True,
                    "config": self.server.config.public_dict(),
                    "codex_version": self.server.codex_version,
                    "lan": self._lan_info(),
                    "user": {"name": user_name},
                    "workspaces": [workspace.public_dict() for workspace in self._visible_workspaces(token, user_name)],
                    "jobs": [job.public_dict() for job in self._visible_jobs(token, user_name)],
                }
            )
            return

        if method == "GET" and path == "/api/capabilities":
            self.server.tokens.require(token, "read")
            self._json(
                {
                    "ok": True,
                    "modes": sorted(ALLOWED_MODES),
                    "mode_details": MODE_DESCRIPTIONS,
                    "scopes": ["read", "run", "admin"],
                    "limits": {
                        "max_concurrent_jobs": self.server.config.max_concurrent_jobs,
                        "default_timeout_seconds": self.server.config.default_timeout_seconds,
                    },
                    "security": self.server.config.public_dict()["security"],
                }
            )
            return

        if method == "GET" and path == "/api/workspaces":
            self.server.tokens.require(token, "read")
            self._json({"ok": True, "workspaces": [workspace.public_dict() for workspace in self._visible_workspaces(token, user_name)]})
            return

        if method == "POST" and path == "/api/server/stop":
            if not self._is_loopback_client():
                raise PermissionError("Server stop is only available from this computer.")
            self.server.tokens.require(token, "admin")
            self._json({"ok": True, "status": "stopping"})
            threading.Thread(target=self.server.shutdown, daemon=True, name="codex-bridge-shutdown").start()
            return

        if method == "POST" and path == "/api/workspaces":
            self.server.tokens.require(token, "admin")
            body = self._body()
            body.setdefault("owner", user_name)
            workspace = self.server.config.upsert_workspace(body)
            self._json({"ok": True, "workspace": workspace.public_dict()}, HTTPStatus.CREATED)
            return

        if path.startswith("/api/workspaces/") and path.endswith("/codex-config"):
            parts = [part for part in path.split("/") if part]
            workspace_id = sanitize_id(unquote(parts[2])) if len(parts) >= 4 else ""
            workspace = self._find_workspace(token, workspace_id, user_name)
            self.server.tokens.require(token, "admin", workspace.id)
            config_path = workspace.codex_home / "config.toml"
            if method == "GET":
                text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
                self._json({"ok": True, "workspace_id": workspace.id, "path": str(config_path), "text": text})
                return
            if method == "POST":
                body = self._body()
                config_path.parent.mkdir(parents=True, exist_ok=True)
                config_path.write_text(str(body.get("text") or ""), encoding="utf-8")
                self._json({"ok": True, "workspace_id": workspace.id, "path": str(config_path)})
                return

        if method == "DELETE" and path.startswith("/api/workspaces/"):
            self.server.tokens.require(token, "admin")
            workspace_id = sanitize_id(unquote(path.split("/")[-1]))
            self._json({"ok": self.server.config.remove_workspace(workspace_id)})
            return

        if method == "GET" and path == "/api/chats":
            self.server.tokens.require(token, "read")
            workspace_id = (query.get("workspace_id") or [""])[0]
            if workspace_id:
                workspace = self._find_workspace(token, workspace_id, user_name)
                workspace_id = workspace.id
            chats = self.server.jobs.list_chats(workspace_id, user_name, include_all=token.has_scope("admin"))
            self._json({"ok": True, "chats": chats})
            return

        if method == "POST" and path == "/api/chats":
            self.server.tokens.require(token, "run")
            body = self._body()
            workspace = self._find_workspace(token, body.get("workspace_id"), user_name)
            self.server.tokens.require(token, "run", workspace.id)
            chat = self.server.jobs.upsert_chat(
                workspace.id,
                str(body.get("chat_id") or ""),
                str(body.get("name") or body.get("chat_name") or ""),
                user_name,
                str(body.get("session_id") or ""),
            )
            self._json({"ok": True, "chat": chat}, HTTPStatus.CREATED)
            return

        if method == "GET" and path == "/api/tokens":
            self.server.tokens.require(token, "admin")
            self._json({"ok": True, "tokens": [record.public_dict() for record in self.server.tokens.records()]})
            return

        if method == "POST" and path == "/api/tokens":
            self.server.tokens.require(token, "admin")
            body = self._body()
            new_token, record = self.server.tokens.create_token(
                str(body.get("name") or "Bridge token"),
                list(body.get("scopes") or ["read", "run"]),
                list(body.get("workspaces") or ["*"]),
                body.get("ttl_days"),
            )
            self._json({"ok": True, "token": new_token, "record": record.public_dict()}, HTTPStatus.CREATED)
            return

        if method == "DELETE" and path.startswith("/api/tokens/"):
            self.server.tokens.require(token, "admin")
            token_id = unquote(path.split("/")[-1])
            self._json({"ok": self.server.tokens.revoke(token_id)})
            return

        if method == "GET" and path == "/api/jobs":
            self.server.tokens.require(token, "read")
            jobs = self._visible_jobs(token, user_name)
            self._json({"ok": True, "jobs": [job.public_dict() for job in jobs]})
            return

        if method == "GET" and path == "/api/audit":
            self.server.tokens.require(token, "admin")
            limit = int((query.get("limit") or ["100"])[0])
            self._json({"ok": True, "entries": self.server.jobs.audit_entries(limit)})
            return

        if method == "POST" and path == "/api/jobs":
            body = self._body()
            workspace = self._require_workspace(token, body.get("workspace_id"), user_name)
            mode = str(body.get("mode") or "exec").strip().lower()
            if body.get("chat_id") and mode in {"exec-resume", "resume", "fork"} and not body.get("session_id"):
                session_id = self.server.jobs.chat_session_id(workspace.id, str(body.get("chat_id")), user_name)
                if session_id:
                    body["session_id"] = session_id
            required_scope = "admin" if mode in ADMIN_MODES else "run"
            self.server.tokens.require(token, required_scope, workspace.id)
            job = self.server.jobs.create_job(workspace, mode, body, token, user_name)
            self._json({"ok": True, "job": job.public_dict()}, HTTPStatus.ACCEPTED)
            return

        if path.startswith("/api/jobs/"):
            parts = [part for part in path.split("/") if part]
            job_id = parts[2] if len(parts) >= 3 else ""
            job = self.server.jobs.get_job(job_id)
            if job is None:
                raise FileNotFoundError()
            self.server.tokens.require(token, "read", job.workspace_id)
            if not self._job_user_allowed(token, job, user_name):
                raise PermissionError("Job belongs to another user.")
            if method == "GET" and len(parts) == 3:
                self._json({"ok": True, "job": job.public_dict()})
                return
            if method == "GET" and len(parts) == 4 and parts[3] == "events":
                since = int((query.get("since") or ["0"])[0])
                self._json({"ok": True, "events": self.server.jobs.events(job_id, since)})
                return
            if method == "GET" and len(parts) == 4 and parts[3] == "stream":
                self._stream(job_id, int((query.get("since") or ["0"])[0]))
                return
            if method == "POST" and len(parts) == 4 and parts[3] == "cancel":
                self.server.tokens.require(token, "run", job.workspace_id)
                self._json({"ok": self.server.jobs.cancel_job(job_id)})
                return

        if method == "POST" and path == "/api/codex/doctor":
            body = self._body()
            workspace = self._require_workspace(token, body.get("workspace_id"), user_name)
            self.server.tokens.require(token, "run", workspace.id)
            body["mode"] = "doctor"
            job = self.server.jobs.create_job(workspace, "doctor", body, token, user_name)
            self._json({"ok": True, "job": job.public_dict()}, HTTPStatus.ACCEPTED)
            return

        if method == "POST" and path == "/api/codex/review":
            body = self._body()
            workspace = self._require_workspace(token, body.get("workspace_id"), user_name)
            self.server.tokens.require(token, "run", workspace.id)
            body["mode"] = "review"
            job = self.server.jobs.create_job(workspace, "review", body, token, user_name)
            self._json({"ok": True, "job": job.public_dict()}, HTTPStatus.ACCEPTED)
            return

        raise FileNotFoundError()

    def _visible_workspaces(self, token: TokenRecord, user_name: str) -> list[Any]:
        return [
            workspace
            for workspace in self.server.config.workspaces()
            if workspace.enabled
            and token.has_workspace(workspace.id)
            and self._workspace_user_allowed(token, workspace, user_name)
        ]

    def _visible_jobs(self, token: TokenRecord, user_name: str) -> list[Any]:
        return [
            job
            for job in self.server.jobs.list_jobs()
            if token.has_workspace(job.workspace_id) and self._job_user_allowed(token, job, user_name)
        ]

    def _lan_info(self) -> dict[str, Any]:
        host = self.server.config.server_host
        port = self.server.config.server_port
        hostname = socket.gethostname()
        addresses: set[str] = set()
        try:
            for item in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
                address = item[4][0]
                if address and not address.startswith("127."):
                    addresses.add(address)
        except OSError:
            pass
        if host not in {"0.0.0.0", "127.0.0.1", "localhost", "::"}:
            addresses.add(host)
        scheme = "https" if self.server.config.tls_config().get("enabled") else "http"
        bridge_urls = [f"{scheme}://{address}:{port}" for address in sorted(addresses)]
        ui_urls = [f"{url}/ui" for url in bridge_urls] if self.server.config.allow_lan_static_ui else []
        return {
            "hostname": hostname,
            "addresses": sorted(addresses),
            "bridge_urls": bridge_urls,
            "ui_urls": ui_urls,
            "loopback_ui_url": f"{scheme}://127.0.0.1:{port}/ui",
            "direct_static_ui_enabled": self.server.config.allow_lan_static_ui,
        }

    def _require_workspace(self, token: TokenRecord, workspace_id: Any, user_name: str) -> Any:
        workspace = self._find_workspace(token, workspace_id, user_name)
        if not workspace.path.exists():
            raise ValueError(f"Workspace path does not exist: {workspace.path}")
        return workspace

    def _find_workspace(self, token: TokenRecord, workspace_id: Any, user_name: str) -> Any:
        if workspace_id in (None, ""):
            visible = self._visible_workspaces(token, user_name)
            if not visible:
                raise FileNotFoundError()
            return visible[0]
        workspace = self.server.config.get_workspace(str(workspace_id or ""))
        if workspace is None:
            raise FileNotFoundError()
        self.server.tokens.require(token, "read", workspace.id)
        if not self._workspace_user_allowed(token, workspace, user_name):
            raise PermissionError("Workspace belongs to another user.")
        return workspace

    def _workspace_user_allowed(self, token: TokenRecord, workspace: Any, user_name: str) -> bool:
        if token.has_scope("admin"):
            return True
        owner = normalize_user_name(getattr(workspace, "owner", "") or "")
        return not owner or owner == normalize_user_name(user_name)

    def _job_user_allowed(self, token: TokenRecord, job: Any, user_name: str) -> bool:
        if token.has_scope("admin"):
            return True
        creator = normalize_user_name(getattr(job, "created_by_name", "") or "")
        return not creator or creator == normalize_user_name(user_name)

    def _request_user_name(self, token: TokenRecord) -> str:
        header_name = " ".join(unquote(self.headers.get("X-Codex-Bridge-User") or "").split())
        if token.id.startswith("trusted-"):
            return header_name or "Локальный админ"
        return token.name or header_name or token.id

    def _authenticated(self) -> TokenRecord:
        header = self.headers.get("Authorization", "")
        token = header.removeprefix("Bearer").strip() if header.lower().startswith("bearer ") else ""
        if token:
            record = self.server.tokens.authenticate(token)
            if record is None:
                raise PermissionError("Invalid bearer token.")
            return record
        if not self.server.config.require_api_tokens:
            if self._is_loopback_client():
                if self.server.config.allow_loopback_admin_without_token:
                    return self._trusted_record("loopback-admin", ("admin", "read", "run"))
                if self.server.config.allow_loopback_without_token:
                    return self._trusted_record("loopback", self.server.config.no_auth_scopes)
            if self.server.config.allow_lan_without_token:
                return self._trusted_record("lan-no-auth", self.server.config.no_auth_scopes)
            raise PermissionError("Bearer token required for LAN API access.")
        if self.server.config.allow_loopback_without_token and self._is_loopback_client():
            return self._trusted_record("loopback", ("admin", "read", "run"))
        raise PermissionError("Invalid or missing bearer token.")

    def _trusted_record(self, reason: str, scopes: tuple[str, ...]) -> TokenRecord:
        return TokenRecord(
            id=f"trusted-{reason}",
            name=f"Trusted {reason}",
            hash="",
            scopes=scopes,
            workspaces=("*",),
            created_at=iso_now(),
            expires_at=None,
            last_used_at=None,
            disabled=False,
        )

    def _is_loopback_client(self) -> bool:
        host = self.client_address[0] if self.client_address else ""
        return host in {"127.0.0.1", "::1", "localhost"} or host.startswith("127.")

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Request JSON body must be an object.")
        return data

    def _stream(self, job_id: str, since: int) -> None:
        self.send_response(HTTPStatus.OK)
        self._cors_headers()
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        cursor = since
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            events = self.server.jobs.events(job_id, cursor)
            for event in events:
                self.wfile.write(f"id: {event['index']}\n".encode("utf-8"))
                self.wfile.write(b"event: log\n")
                payload = json.dumps(event, ensure_ascii=False)
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                cursor = int(event["index"]) + 1
            job = self.server.jobs.get_job(job_id)
            if job is None or job.status in {"completed", "failed", "cancelled"}:
                self.wfile.write(b"event: done\ndata: {}\n\n")
                break
            self.wfile.flush()
            time.sleep(1)

    def _static(self, path: str) -> None:
        if not self._is_loopback_client() and not self.server.config.allow_lan_static_ui:
            raise PermissionError(
                "Direct bridge UI is disabled for LAN clients. "
                "Use the GitHub Pages UI with a bridge token or set security.allow_lan_static_ui=true explicitly."
            )
        static_dir = self.server.config.static_dir
        relative = "index.html" if path in {"/", "/ui"} else path.removeprefix("/ui/").removeprefix("/")
        target = (static_dir / relative).resolve()
        if static_dir.resolve() not in (target, *target.parents):
            raise FileNotFoundError()
        if target.is_dir():
            target = target / "index.html"
        if not target.exists():
            target = static_dir / "index.html"
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self._cors_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _cors_headers(self) -> None:
        origin = self.headers.get("Origin")
        allowed = self.server.config.allowed_origins
        if "*" in allowed:
            self.send_header("Access-Control-Allow-Origin", "*")
        elif origin and self._origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        if self.server.config.enable_private_network_cors:
            self.send_header("Access-Control-Allow-Private-Network", "true")

    def _origin_allowed(self, origin: str) -> bool:
        if origin in self.server.config.allowed_origins:
            return True
        return any(fnmatch.fnmatchcase(origin, pattern) for pattern in self.server.config.allowed_origin_patterns)


def create_httpd(config: BridgeConfig) -> tuple[BridgeHTTPServer, str]:
    config.ensure_runtime_dirs()
    address = (config.server_host, config.server_port)
    httpd = BridgeHTTPServer(address, BridgeHandler, config)
    tls = config.tls_config()
    scheme = "http"
    if tls.get("enabled"):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(tls.get("cert_file")), str(tls.get("key_file")))
        httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
        scheme = "https"
    return httpd, scheme


def run_server(config: BridgeConfig) -> None:
    httpd, scheme = create_httpd(config)
    bootstrap_note = ""
    if httpd.bootstrap_token:
        bootstrap_note = f"\nСтартовый админ-токен сохранен в: {config.state_dir / 'bootstrap-admin-token.txt'}"
    print(f"Codex bridge listening on {scheme}://{config.server_host}:{config.server_port}{bootstrap_note}")
    httpd.serve_forever()
