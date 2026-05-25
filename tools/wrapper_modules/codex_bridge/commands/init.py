from __future__ import annotations

import argparse
from pathlib import Path

from wrapper_modules.codex_bridge.core.config import initialize_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize local Codex bridge config/state.")
    parser.add_argument("--config", default=".codex-bridge/server.json", help="Bridge JSON config path.")
    parser.add_argument("--overwrite", action="store_true", help="Rewrite an existing config file.")
    parser.add_argument("--require-tokens", action="store_true", help="Keep bearer-token auth enabled and issue bootstrap admin token.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = initialize_config(Path(args.config), overwrite=args.overwrite)
    if args.require_tokens:
        config.raw["security"]["require_api_tokens"] = True
        config.save()
    config.ensure_runtime_dirs()
    print(f"Config: {config.config_path}")
    print(f"State: {config.state_dir}")
    if config.require_api_tokens:
        from wrapper_modules.codex_bridge.core.auth import TokenStore

        store = TokenStore(config.state_dir / "tokens.json")
        bootstrap = store.ensure_bootstrap_admin(config.state_dir / "bootstrap-admin-token.txt")
        if bootstrap:
            print(f"Стартовый админ-токен: {bootstrap}")
            print(f"Token file: {config.state_dir / 'bootstrap-admin-token.txt'}")
        else:
            print("Стартовый админ-токен уже существует.")
    else:
        print("Bearer token auth is disabled in config; LAN no-token access still requires security.allow_lan_without_token=true.")
    return 0
