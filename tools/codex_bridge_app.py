#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from wrapper_modules.codex_bridge.commands.serve import main as serve_main
from wrapper_modules.codex_bridge.core.tray_app import main as tray_main


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--headless":
        return serve_main(args[1:])
    return tray_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
