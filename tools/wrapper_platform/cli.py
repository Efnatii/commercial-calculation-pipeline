from __future__ import annotations

import argparse
import sys

from wrapper_platform.registry import get_command, list_modules


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a command from an external wrapper module.")
    parser.add_argument("module", nargs="?", help="Module id, for example: rag-anything.")
    parser.add_argument("command", nargs="?", help="Command name, for example: check or visual.")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to the module command.")
    parser.add_argument("--list", action="store_true", help="List registered modules and commands.")
    return parser


def print_modules() -> None:
    for module in list_modules():
        commands = ", ".join(command.name for command in module.commands)
        print(f"{module.id}: {module.title} ({commands})")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list or not args.module:
        print_modules()
        return 0
    if not args.command:
        print(f"Missing command for module {args.module}.", file=sys.stderr)
        return 2
    command = get_command(args.module, args.command)
    if command is None:
        print(f"Unknown wrapper command: {args.module} {args.command}", file=sys.stderr)
        return 2
    passthrough = args.args
    if passthrough and passthrough[0] == "--":
        passthrough = passthrough[1:]
    return command.main(passthrough)


if __name__ == "__main__":
    raise SystemExit(main())
