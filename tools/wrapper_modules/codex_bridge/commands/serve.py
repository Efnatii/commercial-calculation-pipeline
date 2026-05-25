from __future__ import annotations

import argparse
from pathlib import Path

from wrapper_modules.codex_bridge.core.config import BridgeConfig
from wrapper_modules.codex_bridge.core.server import run_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local Codex bridge HTTP server.")
    parser.add_argument("--config", default=".codex-bridge/server.json", help="Bridge JSON config path.")
    parser.add_argument("--host", help="Override listen host.")
    parser.add_argument("--port", type=int, help="Override listen port.")
    parser.add_argument(
        "--no-auth",
        action="store_true",
        help="Disable mandatory tokens for loopback callers. LAN callers still need tokens unless explicitly allowed.",
    )
    parser.add_argument("--require-tokens", action="store_true", help="Require API bearer tokens for non-health calls.")
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
    parser.add_argument(
        "--no-loopback-bypass",
        action="store_true",
        help="Require bearer tokens even for 127.0.0.1 API callers.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = BridgeConfig.load(Path(args.config))
    config_missing = config.config_path is not None and not config.config_path.exists()
    if args.host:
        config.raw["server"]["host"] = args.host
    if args.port:
        config.raw["server"]["port"] = args.port
    if args.no_auth and args.require_tokens:
        raise ValueError("--no-auth and --require-tokens cannot be used together.")
    if args.no_auth:
        config.raw["security"]["require_api_tokens"] = False
    if args.require_tokens:
        config.raw["security"]["require_api_tokens"] = True
        config.raw["security"]["allow_loopback_without_token"] = False
        config.raw["security"]["allow_loopback_admin_without_token"] = False
    if args.allow_lan_no_token:
        config.raw["security"]["allow_lan_without_token"] = True
        if not config.raw["security"].get("no_auth_scopes"):
            config.raw["security"]["no_auth_scopes"] = ["read", "run"]
    if args.allow_lan_static_ui:
        config.raw["security"]["allow_lan_static_ui"] = True
    if args.no_loopback_bypass:
        config.raw["security"]["allow_loopback_without_token"] = False
        config.raw["security"]["allow_loopback_admin_without_token"] = False
    if config.config_path is not None and config_missing:
        config.save()
    run_server(config)
    return 0
