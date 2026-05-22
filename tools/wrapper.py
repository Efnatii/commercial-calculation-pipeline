#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from wrapper_platform.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
