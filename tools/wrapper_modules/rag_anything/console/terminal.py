from __future__ import annotations

import os
import time
from pathlib import Path

from wrapper_modules.rag_anything.core.paths import find_project_root

def project_root() -> Path:
    return find_project_root()

def terminal_width(default: int = 118) -> int:
    try:
        return max(90, min(150, os.get_terminal_size().columns))
    except OSError:
        return default

def sleep_frame(seconds: float) -> None:
    try:
        time.sleep(seconds)
    except KeyboardInterrupt:
        raise

__all__ = ["project_root", "terminal_width", "sleep_frame"]
