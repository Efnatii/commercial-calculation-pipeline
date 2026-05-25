from __future__ import annotations

import argparse
import json
import sys
import threading
from pathlib import Path
from typing import Any
from urllib import request

from wrapper_modules.codex_bridge.core.config import BridgeConfig
from wrapper_modules.codex_bridge.core.server import BridgeHTTPServer, create_httpd


class ManagedBridge:
    def __init__(
        self,
        config_path: Path,
        host: str,
        port: int,
        require_tokens: bool,
        loopback_bypass: bool,
        allow_lan_static_ui: bool,
        allow_lan_no_token: bool,
    ):
        self.config_path = config_path
        self.host = host
        self.port = port
        self.require_tokens = require_tokens
        self.loopback_bypass = loopback_bypass
        self.allow_lan_static_ui = allow_lan_static_ui
        self.allow_lan_no_token = allow_lan_no_token
        self.config = self._load_config()
        self.httpd: BridgeHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.scheme = "http"

    def _load_config(self) -> BridgeConfig:
        config = BridgeConfig.load(self.config_path)
        missing = config.config_path is not None and not config.config_path.exists()
        config.raw["server"]["host"] = self.host
        config.raw["server"]["port"] = self.port
        config.raw["security"]["require_api_tokens"] = self.require_tokens
        config.raw["security"]["allow_loopback_without_token"] = self.loopback_bypass
        config.raw["security"]["allow_loopback_admin_without_token"] = self.loopback_bypass
        config.raw["security"]["allow_lan_without_token"] = self.allow_lan_no_token
        config.raw["security"]["allow_lan_static_ui"] = self.allow_lan_static_ui
        if self.allow_lan_no_token and not config.raw["security"].get("no_auth_scopes"):
            config.raw["security"]["no_auth_scopes"] = ["read", "run"]
        if missing and config.config_path is not None:
            config.save()
        return config

    @property
    def local_base_url(self) -> str:
        return f"{self.scheme}://127.0.0.1:{self.port}"

    @property
    def ui_url(self) -> str:
        return f"{self.local_base_url}/ui"

    def start(self) -> None:
        if self.httpd is not None:
            return
        self.config = self._load_config()
        self.httpd, self.scheme = create_httpd(self.config)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True, name="codex-bridge-webview-server")
        self.thread.start()

    def stop(self) -> None:
        httpd = self.httpd
        if httpd is None:
            return
        httpd.shutdown()
        httpd.server_close()
        self.httpd = None
        self.thread = None

    def restart(self) -> None:
        self.stop()
        self.start()

    def health(self) -> dict[str, Any]:
        with request.urlopen(f"{self.local_base_url}/health", timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))


class NativeWebViewConsole:
    def __init__(self, bridge: ManagedBridge, start_hidden: bool):
        self.bridge = bridge
        self.start_hidden = start_hidden
        self.window = None
        self.tray_icon = None
        self.quitting = False

    def run(self) -> int:
        import webview

        self.bridge.start()
        self.tray_icon = self._start_tray_icon()
        self.window = webview.create_window(
            "Codex Bridge",
            url=self.bridge.ui_url,
            width=1280,
            height=860,
            min_size=(980, 640),
            background_color="#f5f7fb",
            text_select=True,
        )
        if self.window is None:
            raise RuntimeError("Could not create Codex Bridge WebView window.")
        self.window.events.closing += self._on_window_closing
        self.window.events.loaded += self._on_loaded
        webview.start(gui="edgechromium", private_mode=False, storage_path=str(self.bridge.config.state_dir / "webview"))
        self._shutdown_tray()
        self.bridge.stop()
        return 0

    def _on_loaded(self) -> None:
        if self.start_hidden:
            self.hide_window()

    def _on_window_closing(self) -> bool:
        if self.quitting:
            return True
        self.hide_window()
        return False

    def _start_tray_icon(self) -> Any:
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError:
            return None

        image = self._tray_image(Image, ImageDraw)
        menu = pystray.Menu(
            pystray.MenuItem("Open Codex Bridge", lambda _icon, _item: self.show_window()),
            pystray.MenuItem("Hide Window", lambda _icon, _item: self.hide_window()),
            pystray.MenuItem("Restart Server", lambda _icon, _item: self.restart_server()),
            pystray.MenuItem("Stop Server", lambda _icon, _item: self.stop_server()),
            pystray.MenuItem("Quit", lambda _icon, _item: self.quit()),
        )
        icon = pystray.Icon("codex-bridge", image, "Codex Bridge", menu)
        threading.Thread(target=icon.run, daemon=True, name="codex-bridge-tray-icon").start()
        return icon

    def _tray_image(self, image_module: Any, draw_module: Any) -> Any:
        bundled_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[4]))
        candidates = [
            bundled_root / "docs" / "codex-ui" / "assets" / "codex-bridge-icon-64.png",
            Path(__file__).resolve().parents[4] / "docs" / "codex-ui" / "assets" / "codex-bridge-icon-64.png",
        ]
        for candidate in candidates:
            if candidate.exists():
                return image_module.open(candidate).convert("RGBA").resize((64, 64))
        image = image_module.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = draw_module.Draw(image)
        draw.rounded_rectangle((8, 8, 56, 56), radius=14, fill=(11, 122, 117, 255))
        draw.line((18, 40, 28, 24, 36, 38, 46, 20), fill=(255, 255, 255, 255), width=4)
        return image

    def _shutdown_tray(self) -> None:
        if self.tray_icon is not None:
            self.tray_icon.stop()
            self.tray_icon = None

    def show_window(self) -> None:
        if self.window is None:
            return
        self.window.show()
        self.window.load_url(self.bridge.ui_url)

    def hide_window(self) -> None:
        if self.window is not None:
            self.window.hide()

    def restart_server(self) -> None:
        self.bridge.restart()
        if self.window is not None:
            self.window.load_url(self.bridge.ui_url)

    def stop_server(self) -> None:
        self.bridge.stop()
        if self.window is not None:
            self.window.load_html(
                "<html><body style='font-family:Segoe UI;padding:32px'>"
                "<h1>Codex Bridge stopped</h1>"
                "<p>Use the tray icon to restart the server or quit the app.</p>"
                "</body></html>"
            )

    def quit(self) -> None:
        self.quitting = True
        self.bridge.stop()
        self._shutdown_tray()
        if self.window is not None:
            self.window.destroy()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Codex Bridge as a native Windows WebView2 tray application.")
    parser.add_argument("--config", default=".codex-bridge/server.json", help="Bridge JSON config path.")
    parser.add_argument("--host", default="0.0.0.0", help="Listen host.")
    parser.add_argument("--port", type=int, default=8765, help="Listen port.")
    parser.add_argument(
        "--require-tokens",
        action="store_true",
        help="Require bearer tokens even for the local WebView API calls.",
    )
    parser.add_argument(
        "--no-auth",
        action="store_true",
        help="Disable mandatory tokens for loopback callers. LAN callers still need tokens unless explicitly allowed.",
    )
    parser.add_argument(
        "--allow-lan-no-token",
        action="store_true",
        help="Explicitly allow unauthenticated LAN API calls using security.no_auth_scopes.",
    )
    parser.add_argument(
        "--allow-lan-static-ui",
        action="store_true",
        help="Explicitly serve the bridge-hosted /ui page to non-loopback LAN clients.",
    )
    parser.add_argument("--hidden", action="store_true", help="Start hidden in the tray.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.no_auth and args.require_tokens:
        raise ValueError("--no-auth and --require-tokens cannot be used together.")
    bridge = ManagedBridge(
        Path(args.config),
        args.host,
        args.port,
        require_tokens=not args.no_auth,
        loopback_bypass=not args.require_tokens,
        allow_lan_static_ui=args.allow_lan_static_ui,
        allow_lan_no_token=args.allow_lan_no_token,
    )
    return NativeWebViewConsole(bridge, start_hidden=args.hidden).run()
