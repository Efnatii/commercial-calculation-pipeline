from __future__ import annotations

import json
import re
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from wrapper_modules.codex_bridge.core.auth import TokenStore
from wrapper_modules.codex_bridge.core.codex import ALLOWED_MODES, ADMIN_MODES, MODE_DESCRIPTIONS, CodexCommandBuilder
from wrapper_modules.codex_bridge.core.config import BridgeConfig, DEFAULT_CONFIG, deep_merge, read_json
from wrapper_modules.codex_bridge.core.server import BridgeHTTPServer, BridgeHandler


class CodexBridgeCoreTests(unittest.TestCase):
    def make_config(self, tmp: Path) -> BridgeConfig:
        raw = deep_merge(
            DEFAULT_CONFIG,
            {
                "server": {"host": "127.0.0.1", "port": 0},
                "runtime": {
                    "state_dir": str(tmp / "state"),
                    "static_dir": str(ROOT / "docs" / "codex-ui"),
                    "codex_command": "codex",
                    "max_concurrent_jobs": 1,
                },
                "security": {"require_api_tokens": True, "allow_loopback_without_token": False},
                "workspaces": [
                    {
                        "id": "main",
                        "name": "Main",
                        "path": str(tmp),
                        "codex_home": str(tmp / "state" / "workspaces" / "main" / "codex-home"),
                        "enabled": True,
                    }
                ],
            },
        )
        return BridgeConfig(raw, tmp, tmp / "server.json")

    def test_token_store_creates_and_authenticates_scoped_token(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "tokens.json"
            store = TokenStore(path)
            token, record = store.create_token("test", ["read"], ["main"])

            self.assertTrue(token.startswith("cxb_"))
            self.assertEqual(record.scopes, ("read",))
            authenticated = store.authenticate(token)
            self.assertIsNotNone(authenticated)
            assert authenticated is not None
            self.assertTrue(authenticated.has_workspace("main"))
            self.assertFalse(authenticated.has_workspace("other"))

    def test_token_store_persists_plaintext_machine_token(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "tokens.json"
            token_file = Path(td) / "current-machine-token.txt"
            store = TokenStore(path)

            token, record, created = store.ensure_plaintext_token(
                token_file,
                "machine",
                ["read", "run"],
                ["*"],
            )
            second_token, second_record, second_created = store.ensure_plaintext_token(
                token_file,
                "machine",
                ["read", "run"],
                ["*"],
            )

            self.assertTrue(created)
            self.assertFalse(second_created)
            self.assertEqual(token, second_token)
            self.assertEqual(record.id, second_record.id)
            self.assertEqual(token_file.read_text(encoding="utf-8").strip(), token)
            authenticated = store.authenticate(token)
            self.assertIsNotNone(authenticated)
            assert authenticated is not None
            self.assertTrue(authenticated.has_scope("run"))

    def test_command_builder_exec_uses_workspace_container_and_blocks_danger(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            config = self.make_config(tmp)
            workspace = config.get_workspace("main")
            assert workspace is not None
            command, stdin = CodexCommandBuilder(config).build(
                workspace,
                "exec",
                {"prompt": "say ok", "sandbox": "read-only", "approval_policy": "never"},
            )

            self.assertEqual(stdin, "say ok")
            self.assertIn("exec", command)
            self.assertIn("--json", command)
            self.assertIn("--cd", command)
            self.assertIn(str(tmp.resolve()), command)

            with self.assertRaises(ValueError):
                CodexCommandBuilder(config).build(
                    workspace,
                    "exec",
                    {"prompt": "unsafe", "sandbox": "danger-full-access", "approval_policy": "never"},
                )

    def test_command_builder_covers_codex_management_modes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            config = self.make_config(tmp)
            workspace = config.get_workspace("main")
            assert workspace is not None
            builder = CodexCommandBuilder(config)

            command, _ = builder.build(workspace, "mcp-list", {})
            self.assertEqual(command[-3:], ["mcp", "list", "--json"])

            command, _ = builder.build(workspace, "mcp-get", {"name": "local-tools"})
            self.assertEqual(command[-4:], ["mcp", "get", "--json", "local-tools"])

            command, _ = builder.build(workspace, "plugin-list", {"marketplace": "debug"})
            self.assertIn("plugin", command)
            self.assertIn("--marketplace", command)

            command, _ = builder.build(workspace, "features-list", {})
            self.assertEqual(command[-2:], ["features", "list"])

            command, _ = builder.build(workspace, "app-daemon-version", {})
            self.assertEqual(command[-3:], ["app-server", "daemon", "version"])

            command, _ = builder.build(workspace, "exec-resume", {"last": True, "prompt": "continue"})
            self.assertIn("resume", command)
            self.assertIn("--last", command)
            self.assertEqual(command[-1], "-")

            command, _ = builder.build(workspace, "login-status", {})
            self.assertEqual(command[-2:], ["login", "status"])

            command, stdin = builder.build(workspace, "login-api-key", {"secret": "sk-test"})
            self.assertEqual(command[-1], "--with-api-key")
            self.assertEqual(stdin, "sk-test")

            command, stdin = builder.build(workspace, "login-access-token", {"secret": "access-test"})
            self.assertEqual(command[-1], "--with-access-token")
            self.assertEqual(stdin, "access-test")

            command, stdin = builder.build(workspace, "login-device-auth", {})
            self.assertEqual(command[-1], "--device-auth")
            self.assertEqual(stdin, "")

            command, _ = builder.build(workspace, "mcp-add", {"name": "docs", "url": "http://127.0.0.1:9000/mcp"})
            self.assertIn("--url", command)

            command, _ = builder.build(workspace, "mcp-remove", {"name": "docs"})
            self.assertEqual(command[-3:], ["mcp", "remove", "docs"])

            command, _ = builder.build(workspace, "plugin-add", {"plugin": "sample", "marketplace": "debug"})
            self.assertEqual(command[-4:], ["add", "sample", "--marketplace", "debug"])

            command, _ = builder.build(workspace, "plugin-marketplace-add", {"source": "owner/repo", "ref": "main"})
            self.assertIn("marketplace", command)
            self.assertIn("--ref", command)

            command, _ = builder.build(workspace, "features-enable", {"feature": "unified_exec"})
            self.assertEqual(command[-3:], ["features", "enable", "unified_exec"])

            command, _ = builder.build(workspace, "completion", {"shell": "powershell"})
            self.assertEqual(command[-2:], ["completion", "powershell"])

            command, _ = builder.build(workspace, "debug-models", {"bundled": True})
            self.assertEqual(command[-3:], ["debug", "models", "--bundled"])

            command, _ = builder.build(workspace, "debug-app-server-send-message-v2", {"message": "ping"})
            self.assertEqual(command[-4:], ["debug", "app-server", "send-message-v2", "ping"])

            command, _ = builder.build(workspace, "cloud-list", {"limit": 5})
            self.assertIn("--json", command)
            self.assertIn("--limit", command)

            command, _ = builder.build(workspace, "cloud-status", {"task_id": "task_123"})
            self.assertEqual(command[-3:], ["cloud", "status", "task_123"])

            command, _ = builder.build(workspace, "apply", {"task_id": "task_123"})
            self.assertEqual(command[-2:], ["apply", "task_123"])

            command, _ = builder.build(workspace, "sandbox-windows", {"command": ["cmd", "/c", "echo", "ok"]})
            self.assertIn("windows", command)
            self.assertEqual(command[-4:], ["cmd", "/c", "echo", "ok"])

            command, _ = builder.build(workspace, "sandbox-linux", {"command": ["echo", "ok"]})
            self.assertIn("linux", command)
            self.assertEqual(command[-2:], ["echo", "ok"])

            command, _ = builder.build(workspace, "exec-server-start", {"listen": "ws://127.0.0.1:0"})
            self.assertIn("exec-server", command)

            command, _ = builder.build(workspace, "mcp-server", {})
            self.assertEqual(command[-1], "mcp-server")

            command, _ = builder.build(workspace, "app-open", {"path": str(tmp)})
            self.assertIn("app", command)
            self.assertEqual(command[-1], str(tmp))

            command, _ = builder.build(workspace, "app-server-start", {"listen": "ws://127.0.0.1:0"})
            self.assertIn("app-server", command)
            self.assertIn("--listen", command)

            command, _ = builder.build(workspace, "app-server-proxy", {"sock": str(tmp / "sock")})
            self.assertIn("proxy", command)
            self.assertIn("--sock", command)

            command, _ = builder.build(workspace, "app-daemon-bootstrap", {"remote_control": True})
            self.assertEqual(command[-4:], ["app-server", "daemon", "bootstrap", "--remote-control"])

            command, _ = builder.build(workspace, "app-server-generate-json-schema", {"out_dir": str(tmp / "schema")})
            self.assertIn("generate-json-schema", command)

            with self.assertRaises(ValueError):
                builder.build(workspace, "raw", {"args": ["--help"]})

            config.raw["security"]["allow_raw_codex_args"] = True
            command, stdin = builder.build(workspace, "raw", {"args": ["--help"], "stdin": "input"})
            self.assertEqual(command[-1], "--help")
            self.assertEqual(stdin, "input")

    def test_static_ui_exposes_all_backend_modes(self) -> None:
        html = (ROOT / "docs" / "codex-ui" / "index.html").read_text(encoding="utf-8")
        match = re.search(r'<select id="modeSelect".*?</select>', html, re.DOTALL)
        self.assertIsNotNone(match)
        assert match is not None
        ui_modes = set(re.findall(r'<option value="([^"]+)">', match.group(0)))
        self.assertEqual(ui_modes, ALLOWED_MODES)

    def test_openapi_mode_enum_matches_backend_modes(self) -> None:
        openapi = json.loads((ROOT / "docs" / "codex-bridge-openapi.json").read_text(encoding="utf-8"))
        mode_enum = set(openapi["components"]["schemas"]["JobCreate"]["properties"]["mode"]["enum"])
        self.assertEqual(mode_enum, ALLOWED_MODES)

    def test_openapi_documents_backend_api_paths(self) -> None:
        openapi = json.loads((ROOT / "docs" / "codex-bridge-openapi.json").read_text(encoding="utf-8"))
        documented = set(openapi["paths"])
        expected = {
            "/health",
            "/api/status",
            "/api/capabilities",
            "/api/workspaces",
            "/api/workspaces/{workspaceId}",
            "/api/workspaces/{workspaceId}/codex-config",
            "/api/local-user-token",
            "/api/server/stop",
            "/api/tokens",
            "/api/tokens/{tokenId}",
            "/api/jobs",
            "/api/audit",
            "/api/jobs/{jobId}",
            "/api/jobs/{jobId}/events",
            "/api/jobs/{jobId}/stream",
            "/api/jobs/{jobId}/cancel",
            "/api/codex/doctor",
            "/api/codex/review",
        }
        self.assertTrue(expected.issubset(documented), sorted(expected - documented))

    def test_mode_descriptions_cover_backend_modes(self) -> None:
        self.assertEqual(set(MODE_DESCRIPTIONS), ALLOWED_MODES)
        for mode, details in MODE_DESCRIPTIONS.items():
            self.assertIn(details["scope"], {"read", "run", "admin"}, mode)
            self.assertTrue(details["title"].strip(), mode)
        self.assertEqual(ADMIN_MODES, {mode for mode, details in MODE_DESCRIPTIONS.items() if details["scope"] == "admin"})

    def test_config_json_loader_accepts_windows_utf8_bom(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            config_path = Path(td) / "server.json"
            config_path.write_bytes(b"\xef\xbb\xbf" + json.dumps({"runtime": {"state_dir": "state"}}).encode("utf-8"))
            loaded = read_json(config_path)
            self.assertEqual(loaded["runtime"]["state_dir"], "state")

    def test_example_config_loads_without_machine_specific_paths(self) -> None:
        example_path = ROOT / "configs" / "codex-bridge.example.json"
        raw = read_json(example_path)
        config = BridgeConfig(deep_merge(DEFAULT_CONFIG, raw), ROOT, example_path)

        self.assertEqual(config.server_port, 8765)
        self.assertIn("https://*.github.io", config.allowed_origin_patterns)
        self.assertEqual(config.no_auth_scopes, ())
        self.assertTrue(config.require_api_tokens)
        self.assertFalse(config.allow_lan_without_token)
        self.assertFalse(config.allow_lan_static_ui)
        self.assertFalse(config.allow_lan_health)

        workspaces = config.workspaces()
        self.assertEqual([workspace.id for workspace in workspaces], ["main"])
        self.assertEqual(workspaces[0].path, ROOT.resolve())
        self.assertEqual(workspaces[0].codex_home, (ROOT / ".codex-bridge" / "workspaces" / "main" / "codex-home").resolve())
        self.assertNotIn("C:\\\\Users\\\\", json.dumps(raw))

    def test_github_workflow_covers_bridge_trigger_paths_and_formatting(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "codex-bridge-tests.yml").read_text(encoding="utf-8")
        required_paths = [
            "tools/wrapper_modules/codex_bridge/**",
            "tools/codex_bridge_app.py",
            "tools/codex_bridge_cert.py",
            "configs/codex-bridge.example.json",
            "docs/codex-ui/**",
            "docs/index.html",
            "docs/.nojekyll",
            "docs/codex-bridge*.md",
            "scripts/*codex-bridge*.ps1",
            "tests/test_codex_bridge_core.py",
            "README.md",
        ]
        for path in required_paths:
            self.assertIn(path, workflow)
        self.assertIn("npx --yes prettier --check", workflow)

    def test_health_and_authenticated_status_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            config = self.make_config(tmp)
            config.ensure_runtime_dirs()
            server = BridgeHTTPServer(("127.0.0.1", 0), BridgeHandler, config)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=5) as response:
                    health = json.loads(response.read().decode("utf-8"))
                self.assertTrue(health["ok"])

                request = urllib.request.Request(f"http://{host}:{port}/api/status")
                request.add_header("Authorization", f"Bearer {server.bootstrap_token}")
                with urllib.request.urlopen(request, timeout=5) as response:
                    status = json.loads(response.read().decode("utf-8"))
                self.assertTrue(status["ok"])
                self.assertEqual(status["workspaces"][0]["id"], "main")

                request = urllib.request.Request(f"http://{host}:{port}/api/capabilities")
                request.add_header("Authorization", f"Bearer {server.bootstrap_token}")
                with urllib.request.urlopen(request, timeout=5) as response:
                    capabilities = json.loads(response.read().decode("utf-8"))
                self.assertIn("mcp-list", capabilities["modes"])
                self.assertEqual(capabilities["mode_details"]["raw"]["scope"], "admin")
            finally:
                server.shutdown()
                server.server_close()

    def test_local_user_token_endpoint_issues_loopback_token(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            raw = deep_merge(
                DEFAULT_CONFIG,
                {
                    "server": {"host": "127.0.0.1", "port": 0},
                    "runtime": {
                        "state_dir": str(tmp / "state"),
                        "static_dir": str(ROOT / "docs" / "codex-ui"),
                        "codex_command": "codex",
                        "max_concurrent_jobs": 1,
                    },
                    "security": {
                        "require_api_tokens": True,
                        "allow_loopback_without_token": True,
                        "allow_loopback_admin_without_token": True,
                    },
                    "workspaces": [
                        {
                            "id": "main",
                            "name": "Main",
                            "path": str(tmp),
                            "codex_home": str(tmp / "state" / "workspaces" / "main" / "codex-home"),
                            "enabled": True,
                        }
                    ],
                },
            )
            config = BridgeConfig(raw, tmp, tmp / "server.json")
            config.ensure_runtime_dirs()
            server = BridgeHTTPServer(("127.0.0.1", 0), BridgeHandler, config)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                with urllib.request.urlopen(f"http://{host}:{port}/api/local-user-token", timeout=5) as response:
                    created = json.loads(response.read().decode("utf-8"))
                self.assertTrue(created["ok"])
                self.assertTrue(created["token"].startswith("cxb_"))
                self.assertEqual(created["record"]["name"], "Стартовый админ")
                self.assertEqual(created["record"]["scopes"], ["admin", "read", "run"])
                self.assertTrue((tmp / "state" / "bootstrap-admin-token.txt").exists())
                self.assertFalse((tmp / "state" / "current-machine-token.txt").exists())

                with urllib.request.urlopen(f"http://{host}:{port}/api/local-user-token", timeout=5) as response:
                    reused = json.loads(response.read().decode("utf-8"))
                self.assertEqual(created["token"], reused["token"])
                self.assertFalse(reused["created"])

                request = urllib.request.Request(f"http://{host}:{port}/api/status")
                request.add_header("Authorization", f"Bearer {created['token']}")
                with urllib.request.urlopen(request, timeout=5) as response:
                    status = json.loads(response.read().decode("utf-8"))
                self.assertTrue(status["ok"])

                request = urllib.request.Request(f"http://{host}:{port}/api/tokens")
                request.add_header("Authorization", f"Bearer {created['token']}")
                with urllib.request.urlopen(request, timeout=5) as response:
                    tokens = json.loads(response.read().decode("utf-8"))
                self.assertTrue(tokens["ok"])
            finally:
                server.shutdown()
                server.server_close()

    def test_server_stop_endpoint_shuts_down_loopback_server(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            config = self.make_config(tmp)
            config.ensure_runtime_dirs()
            server = BridgeHTTPServer(("127.0.0.1", 0), BridgeHandler, config)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                body = json.dumps({}).encode("utf-8")
                request = urllib.request.Request(
                    f"http://{host}:{port}/api/server/stop",
                    data=body,
                    method="POST",
                )
                request.add_header("Authorization", f"Bearer {server.bootstrap_token}")
                request.add_header("Content-Type", "application/json")
                with urllib.request.urlopen(request, timeout=5) as response:
                    stopped = json.loads(response.read().decode("utf-8"))
                self.assertTrue(stopped["ok"])
                self.assertEqual(stopped["status"], "stopping")
                thread.join(timeout=5)
                self.assertFalse(thread.is_alive())
            finally:
                server.shutdown()
                server.server_close()

    def test_no_auth_mode_allows_loopback_native_ui_calls(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            raw = deep_merge(
                DEFAULT_CONFIG,
                {
                    "server": {"host": "127.0.0.1", "port": 0},
                    "runtime": {
                        "state_dir": str(tmp / "state"),
                        "static_dir": str(ROOT / "docs" / "codex-ui"),
                        "codex_command": "codex",
                        "max_concurrent_jobs": 1,
                    },
                    "security": {"require_api_tokens": False, "allow_loopback_without_token": True},
                    "workspaces": [
                        {
                            "id": "main",
                            "name": "Main",
                            "path": str(tmp),
                            "codex_home": str(tmp / "state" / "workspaces" / "main" / "codex-home"),
                            "enabled": True,
                        }
                    ],
                },
            )
            config = BridgeConfig(raw, tmp, tmp / "server.json")
            config.ensure_runtime_dirs()
            server = BridgeHTTPServer(("127.0.0.1", 0), BridgeHandler, config)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                with urllib.request.urlopen(f"http://{host}:{port}/api/status", timeout=5) as response:
                    status = json.loads(response.read().decode("utf-8"))
                self.assertTrue(status["ok"])
                self.assertEqual(status["config"]["security"]["no_auth_scopes"], [])

                with urllib.request.urlopen(f"http://{host}:{port}/api/tokens", timeout=5) as response:
                    tokens = json.loads(response.read().decode("utf-8"))
                self.assertTrue(tokens["ok"])
                self.assertIsNotNone(server.bootstrap_token)
                self.assertTrue((tmp / "state" / "bootstrap-admin-token.txt").exists())
            finally:
                server.shutdown()
                server.server_close()

    def test_no_auth_lan_clients_are_denied_without_explicit_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            raw = deep_merge(
                DEFAULT_CONFIG,
                {
                    "server": {"host": "127.0.0.1", "port": 0},
                    "runtime": {
                        "state_dir": str(tmp / "state"),
                        "static_dir": str(ROOT / "docs" / "codex-ui"),
                        "codex_command": "codex",
                        "max_concurrent_jobs": 1,
                    },
                    "security": {"require_api_tokens": False, "allow_loopback_without_token": True},
                    "workspaces": [
                        {
                            "id": "main",
                            "name": "Main",
                            "path": str(tmp),
                            "codex_home": str(tmp / "state" / "workspaces" / "main" / "codex-home"),
                            "enabled": True,
                        }
                    ],
                },
            )
            config = BridgeConfig(raw, tmp, tmp / "server.json")
            config.ensure_runtime_dirs()
            server = BridgeHTTPServer(("127.0.0.1", 0), BridgeHandler, config)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            original_is_loopback = BridgeHandler._is_loopback_client
            BridgeHandler._is_loopback_client = lambda _self: False  # type: ignore[method-assign]
            thread.start()
            try:
                host, port = server.server_address
                with self.assertRaises(urllib.error.HTTPError) as status_error:
                    urllib.request.urlopen(f"http://{host}:{port}/api/status", timeout=5)
                self.assertEqual(status_error.exception.code, 403)

                with self.assertRaises(urllib.error.HTTPError) as token_error:
                    urllib.request.urlopen(f"http://{host}:{port}/api/tokens", timeout=5)
                self.assertEqual(token_error.exception.code, 403)

                workspace_body = json.dumps({"id": "blocked", "path": str(tmp)}).encode("utf-8")
                request = urllib.request.Request(f"http://{host}:{port}/api/workspaces", data=workspace_body, method="POST")
                request.add_header("Content-Type", "application/json")
                with self.assertRaises(urllib.error.HTTPError) as workspace_error:
                    urllib.request.urlopen(request, timeout=5)
                self.assertEqual(workspace_error.exception.code, 403)
            finally:
                BridgeHandler._is_loopback_client = original_is_loopback  # type: ignore[method-assign]
                server.shutdown()
                server.server_close()

    def test_no_auth_lan_clients_can_be_enabled_explicitly_for_read_run_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            raw = deep_merge(
                DEFAULT_CONFIG,
                {
                    "server": {"host": "127.0.0.1", "port": 0},
                    "runtime": {
                        "state_dir": str(tmp / "state"),
                        "static_dir": str(ROOT / "docs" / "codex-ui"),
                        "codex_command": "codex",
                        "max_concurrent_jobs": 1,
                    },
                    "security": {
                        "require_api_tokens": False,
                        "allow_loopback_without_token": True,
                        "allow_lan_without_token": True,
                        "no_auth_scopes": ["read", "run"],
                    },
                    "workspaces": [
                        {
                            "id": "main",
                            "name": "Main",
                            "path": str(tmp),
                            "codex_home": str(tmp / "state" / "workspaces" / "main" / "codex-home"),
                            "enabled": True,
                        }
                    ],
                },
            )
            config = BridgeConfig(raw, tmp, tmp / "server.json")
            config.ensure_runtime_dirs()
            server = BridgeHTTPServer(("127.0.0.1", 0), BridgeHandler, config)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            original_is_loopback = BridgeHandler._is_loopback_client
            BridgeHandler._is_loopback_client = lambda _self: False  # type: ignore[method-assign]
            thread.start()
            try:
                host, port = server.server_address
                with urllib.request.urlopen(f"http://{host}:{port}/api/status", timeout=5) as response:
                    status = json.loads(response.read().decode("utf-8"))
                self.assertTrue(status["ok"])
                self.assertEqual(status["config"]["security"]["no_auth_scopes"], ["read", "run"])
                self.assertTrue(status["config"]["security"]["allow_lan_without_token"])

                with self.assertRaises(urllib.error.HTTPError) as token_error:
                    urllib.request.urlopen(f"http://{host}:{port}/api/tokens", timeout=5)
                self.assertEqual(token_error.exception.code, 403)

                workspace_body = json.dumps({"id": "blocked", "path": str(tmp)}).encode("utf-8")
                request = urllib.request.Request(f"http://{host}:{port}/api/workspaces", data=workspace_body, method="POST")
                request.add_header("Content-Type", "application/json")
                with self.assertRaises(urllib.error.HTTPError) as workspace_error:
                    urllib.request.urlopen(request, timeout=5)
                self.assertEqual(workspace_error.exception.code, 403)
            finally:
                BridgeHandler._is_loopback_client = original_is_loopback  # type: ignore[method-assign]
                server.shutdown()
                server.server_close()

    def test_local_user_token_endpoint_is_loopback_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            raw = deep_merge(
                DEFAULT_CONFIG,
                {
                    "server": {"host": "127.0.0.1", "port": 0},
                    "runtime": {
                        "state_dir": str(tmp / "state"),
                        "static_dir": str(ROOT / "docs" / "codex-ui"),
                        "codex_command": "codex",
                        "max_concurrent_jobs": 1,
                    },
                    "security": {
                        "require_api_tokens": False,
                        "allow_loopback_without_token": True,
                        "allow_lan_without_token": True,
                        "no_auth_scopes": ["read", "run"],
                    },
                    "workspaces": [
                        {
                            "id": "main",
                            "name": "Main",
                            "path": str(tmp),
                            "codex_home": str(tmp / "state" / "workspaces" / "main" / "codex-home"),
                            "enabled": True,
                        }
                    ],
                },
            )
            config = BridgeConfig(raw, tmp, tmp / "server.json")
            config.ensure_runtime_dirs()
            server = BridgeHTTPServer(("127.0.0.1", 0), BridgeHandler, config)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            original_is_loopback = BridgeHandler._is_loopback_client
            BridgeHandler._is_loopback_client = lambda _self: False  # type: ignore[method-assign]
            thread.start()
            try:
                host, port = server.server_address
                with self.assertRaises(urllib.error.HTTPError) as local_token_error:
                    urllib.request.urlopen(f"http://{host}:{port}/api/local-user-token", timeout=5)
                self.assertEqual(local_token_error.exception.code, 403)
                self.assertFalse((tmp / "state" / "current-machine-token.txt").exists())
            finally:
                BridgeHandler._is_loopback_client = original_is_loopback  # type: ignore[method-assign]
                server.shutdown()
                server.server_close()

    def test_bridge_hosted_ui_is_denied_to_lan_clients_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            config = self.make_config(tmp)
            config.ensure_runtime_dirs()
            server = BridgeHTTPServer(("127.0.0.1", 0), BridgeHandler, config)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            original_is_loopback = BridgeHandler._is_loopback_client
            BridgeHandler._is_loopback_client = lambda _self: False  # type: ignore[method-assign]
            thread.start()
            try:
                host, port = server.server_address
                with self.assertRaises(urllib.error.HTTPError) as ui_error:
                    urllib.request.urlopen(f"http://{host}:{port}/ui", timeout=5)
                self.assertEqual(ui_error.exception.code, 403)
            finally:
                BridgeHandler._is_loopback_client = original_is_loopback  # type: ignore[method-assign]
                server.shutdown()
                server.server_close()

    def test_health_is_loopback_only_for_lan_clients_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            config = self.make_config(tmp)
            config.ensure_runtime_dirs()
            server = BridgeHTTPServer(("127.0.0.1", 0), BridgeHandler, config)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            original_is_loopback = BridgeHandler._is_loopback_client
            thread.start()
            try:
                host, port = server.server_address
                with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=5) as response:
                    self.assertEqual(response.status, 200)

                BridgeHandler._is_loopback_client = lambda _self: False  # type: ignore[method-assign]
                with self.assertRaises(urllib.error.HTTPError) as health_error:
                    urllib.request.urlopen(f"http://{host}:{port}/health", timeout=5)
                self.assertEqual(health_error.exception.code, 403)

                config.raw["security"]["allow_lan_health"] = True
                with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=5) as response:
                    self.assertEqual(response.status, 200)
            finally:
                BridgeHandler._is_loopback_client = original_is_loopback  # type: ignore[method-assign]
                server.shutdown()
                server.server_close()

    def test_bridge_hosted_ui_allows_loopback_and_explicit_lan_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            config = self.make_config(tmp)
            config.raw["security"]["allow_lan_static_ui"] = True
            config.ensure_runtime_dirs()
            server = BridgeHTTPServer(("127.0.0.1", 0), BridgeHandler, config)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            original_is_loopback = BridgeHandler._is_loopback_client
            thread.start()
            try:
                host, port = server.server_address
                with urllib.request.urlopen(f"http://{host}:{port}/ui", timeout=5) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn("Управление Bridge".encode("utf-8"), response.read())

                BridgeHandler._is_loopback_client = lambda _self: False  # type: ignore[method-assign]
                with urllib.request.urlopen(f"http://{host}:{port}/ui", timeout=5) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn("Управление Bridge".encode("utf-8"), response.read())
            finally:
                BridgeHandler._is_loopback_client = original_is_loopback  # type: ignore[method-assign]
                server.shutdown()
                server.server_close()

    def test_no_auth_lan_clients_cannot_start_admin_modes_without_token(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            raw = deep_merge(
                DEFAULT_CONFIG,
                {
                    "server": {"host": "127.0.0.1", "port": 0},
                    "runtime": {
                        "state_dir": str(tmp / "state"),
                        "static_dir": str(ROOT / "docs" / "codex-ui"),
                        "codex_command": "codex",
                        "max_concurrent_jobs": 1,
                    },
                    "security": {"require_api_tokens": False, "allow_loopback_without_token": True},
                    "workspaces": [
                        {
                            "id": "main",
                            "name": "Main",
                            "path": str(tmp),
                            "codex_home": str(tmp / "state" / "workspaces" / "main" / "codex-home"),
                            "enabled": True,
                        }
                    ],
                },
            )
            config = BridgeConfig(raw, tmp, tmp / "server.json")
            config.ensure_runtime_dirs()
            server = BridgeHTTPServer(("127.0.0.1", 0), BridgeHandler, config)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            original_is_loopback = BridgeHandler._is_loopback_client
            BridgeHandler._is_loopback_client = lambda _self: False  # type: ignore[method-assign]
            thread.start()
            try:
                host, port = server.server_address
                body = json.dumps({"workspace_id": "main", "mode": "update"}).encode("utf-8")
                request = urllib.request.Request(f"http://{host}:{port}/api/jobs", data=body, method="POST")
                request.add_header("Content-Type", "application/json")
                with self.assertRaises(urllib.error.HTTPError) as job_error:
                    urllib.request.urlopen(request, timeout=5)
                self.assertEqual(job_error.exception.code, 403)
                self.assertEqual(server.jobs.list_jobs(), ())
            finally:
                BridgeHandler._is_loopback_client = original_is_loopback  # type: ignore[method-assign]
                server.shutdown()
                server.server_close()

    def test_no_auth_mode_still_honors_bearer_tokens_for_lan_admin(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            raw = deep_merge(
                DEFAULT_CONFIG,
                {
                    "server": {"host": "127.0.0.1", "port": 0},
                    "runtime": {
                        "state_dir": str(tmp / "state"),
                        "static_dir": str(ROOT / "docs" / "codex-ui"),
                        "codex_command": "codex",
                        "max_concurrent_jobs": 1,
                    },
                    "security": {"require_api_tokens": False, "allow_loopback_without_token": True},
                    "workspaces": [
                        {
                            "id": "main",
                            "name": "Main",
                            "path": str(tmp),
                            "codex_home": str(tmp / "state" / "workspaces" / "main" / "codex-home"),
                            "enabled": True,
                        }
                    ],
                },
            )
            config = BridgeConfig(raw, tmp, tmp / "server.json")
            config.ensure_runtime_dirs()
            server = BridgeHTTPServer(("127.0.0.1", 0), BridgeHandler, config)
            admin_token, _record = server.tokens.create_token("LAN admin", ["admin", "read", "run"], ["*"])
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            original_is_loopback = BridgeHandler._is_loopback_client
            BridgeHandler._is_loopback_client = lambda _self: False  # type: ignore[method-assign]
            thread.start()
            try:
                host, port = server.server_address
                request = urllib.request.Request(f"http://{host}:{port}/api/tokens")
                request.add_header("Authorization", f"Bearer {admin_token}")
                with urllib.request.urlopen(request, timeout=5) as response:
                    tokens = json.loads(response.read().decode("utf-8"))
                self.assertTrue(tokens["ok"])
                self.assertIn("LAN admin", [item["name"] for item in tokens["tokens"]])
            finally:
                BridgeHandler._is_loopback_client = original_is_loopback  # type: ignore[method-assign]
                server.shutdown()
                server.server_close()

    def test_github_pages_origin_pattern_allows_cors(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            config = self.make_config(tmp)
            config.ensure_runtime_dirs()
            server = BridgeHTTPServer(("127.0.0.1", 0), BridgeHandler, config)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                request = urllib.request.Request(f"http://{host}:{port}/api/status")
                request.add_header("Authorization", f"Bearer {server.bootstrap_token}")
                request.add_header("Origin", "https://example.github.io")
                with urllib.request.urlopen(request, timeout=5) as response:
                    self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "https://example.github.io")
                    status = json.loads(response.read().decode("utf-8"))
                self.assertTrue(status["ok"])
                self.assertIn("https://*.github.io", status["config"]["server"]["allowed_origin_patterns"])
            finally:
                server.shutdown()
                server.server_close()

    def test_workspace_codex_config_api_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            config = self.make_config(tmp)
            config.ensure_runtime_dirs()
            server = BridgeHTTPServer(("127.0.0.1", 0), BridgeHandler, config)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                url = f"http://{host}:{port}/api/workspaces/main/codex-config"
                body = json.dumps({"text": 'model = "gpt-5"\n'}).encode("utf-8")
                request = urllib.request.Request(url, data=body, method="POST")
                request.add_header("Authorization", f"Bearer {server.bootstrap_token}")
                request.add_header("Content-Type", "application/json")
                with urllib.request.urlopen(request, timeout=5) as response:
                    saved = json.loads(response.read().decode("utf-8"))
                self.assertTrue(saved["ok"])

                request = urllib.request.Request(url)
                request.add_header("Authorization", f"Bearer {server.bootstrap_token}")
                with urllib.request.urlopen(request, timeout=5) as response:
                    loaded = json.loads(response.read().decode("utf-8"))
                self.assertEqual(loaded["text"], 'model = "gpt-5"\n')
            finally:
                server.shutdown()
                server.server_close()

    def test_admin_workspace_and_token_api_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            config = self.make_config(tmp)
            config.ensure_runtime_dirs()
            server = BridgeHTTPServer(("127.0.0.1", 0), BridgeHandler, config)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                base_url = f"http://{host}:{port}"
                admin_headers = {
                    "Authorization": f"Bearer {server.bootstrap_token}",
                    "Content-Type": "application/json",
                }

                workspace_body = json.dumps(
                    {
                        "id": "client-1",
                        "name": "Client 1",
                        "owner": "Client token",
                        "path": str(tmp),
                        "codex_home": str(tmp / "state" / "workspaces" / "client-1" / "codex-home"),
                        "enabled": True,
                    }
                ).encode("utf-8")
                request = urllib.request.Request(f"{base_url}/api/workspaces", data=workspace_body, method="POST")
                for key, value in admin_headers.items():
                    request.add_header(key, value)
                with urllib.request.urlopen(request, timeout=5) as response:
                    created_workspace = json.loads(response.read().decode("utf-8"))
                self.assertEqual(created_workspace["workspace"]["id"], "client-1")

                token_body = json.dumps(
                    {"name": "Client token", "scopes": ["read", "run"], "workspaces": ["client-1"], "ttl_days": 1}
                ).encode("utf-8")
                request = urllib.request.Request(f"{base_url}/api/tokens", data=token_body, method="POST")
                for key, value in admin_headers.items():
                    request.add_header(key, value)
                with urllib.request.urlopen(request, timeout=5) as response:
                    created_token = json.loads(response.read().decode("utf-8"))
                client_token = created_token["token"]
                token_id = created_token["record"]["id"]

                request = urllib.request.Request(f"{base_url}/api/workspaces")
                request.add_header("Authorization", f"Bearer {client_token}")
                with urllib.request.urlopen(request, timeout=5) as response:
                    visible = json.loads(response.read().decode("utf-8"))
                self.assertEqual([item["id"] for item in visible["workspaces"]], ["client-1"])

                request = urllib.request.Request(f"{base_url}/api/tokens/{token_id}", method="DELETE")
                request.add_header("Authorization", f"Bearer {server.bootstrap_token}")
                with urllib.request.urlopen(request, timeout=5) as response:
                    revoked = json.loads(response.read().decode("utf-8"))
                self.assertTrue(revoked["ok"])

                request = urllib.request.Request(f"{base_url}/api/status")
                request.add_header("Authorization", f"Bearer {client_token}")
                with self.assertRaises(urllib.error.HTTPError):
                    urllib.request.urlopen(request, timeout=5)

                request = urllib.request.Request(f"{base_url}/api/workspaces/client-1", method="DELETE")
                request.add_header("Authorization", f"Bearer {server.bootstrap_token}")
                with urllib.request.urlopen(request, timeout=5) as response:
                    deleted = json.loads(response.read().decode("utf-8"))
                self.assertTrue(deleted["ok"])
            finally:
                server.shutdown()
                server.server_close()

    def test_codex_convenience_endpoints_create_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            config = self.make_config(tmp)
            config.raw["runtime"]["codex_command"] = sys.executable
            config.raw["runtime"]["max_concurrent_jobs"] = 2
            config.ensure_runtime_dirs()
            server = BridgeHTTPServer(("127.0.0.1", 0), BridgeHandler, config)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                base_url = f"http://{host}:{port}"
                headers = {
                    "Authorization": f"Bearer {server.bootstrap_token}",
                    "Content-Type": "application/json",
                }
                for path, mode in (("/api/codex/doctor", "doctor"), ("/api/codex/review", "review")):
                    body = json.dumps({"workspace_id": "main"}).encode("utf-8")
                    request = urllib.request.Request(f"{base_url}{path}", data=body, method="POST")
                    for key, value in headers.items():
                        request.add_header(key, value)
                    with urllib.request.urlopen(request, timeout=5) as response:
                        created = json.loads(response.read().decode("utf-8"))
                    self.assertTrue(created["ok"])
                    self.assertEqual(created["job"]["mode"], mode)
                    self.assertEqual(created["job"]["workspace_id"], "main")
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
