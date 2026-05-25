from __future__ import annotations

import argparse
from pathlib import Path

from wrapper_modules.codex_bridge.core.auth import TokenStore
from wrapper_modules.codex_bridge.core.config import BridgeConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage local Codex bridge tokens.")
    parser.add_argument("--config", default=".codex-bridge/server.json", help="Bridge JSON config path.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List token metadata.")

    create = sub.add_parser("create", help="Create a token and print it once.")
    create.add_argument("--name", default="Bridge token")
    create.add_argument("--scope", action="append", default=[], help="Token scope: read, run, admin.")
    create.add_argument("--workspace", action="append", default=[], help="Allowed workspace id, or *.")
    create.add_argument("--ttl-days", type=int)

    revoke = sub.add_parser("revoke", help="Disable a token by id.")
    revoke.add_argument("token_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = BridgeConfig.load(Path(args.config))
    store = TokenStore(config.state_dir / "tokens.json")
    if args.command == "list":
        for record in store.records():
            status = "disabled" if record.disabled else "active"
            print(f"{record.id}\t{status}\t{record.name}\t{','.join(record.scopes)}\t{','.join(record.workspaces)}")
        return 0
    if args.command == "create":
        token, record = store.create_token(
            args.name,
            args.scope or ["read", "run"],
            args.workspace or ["*"],
            args.ttl_days,
        )
        print(token)
        print(f"id={record.id}")
        return 0
    if args.command == "revoke":
        return 0 if store.revoke(args.token_id) else 1
    return 2

