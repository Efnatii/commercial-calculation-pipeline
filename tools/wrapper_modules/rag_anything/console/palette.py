from __future__ import annotations

import os
import sys

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
FG_OK = "\033[32m"
FG_WARN = "\033[33m"
FG_FAIL = "\033[31m"
FG_SKIP = "\033[36m"
FG_TEXT = "\033[37m"
FG_INFO = "\033[34m"
FG_ACCENT = "\033[35m"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
CLEAR_LINE = "\033[2K\r"

class Palette:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def color(self, text: str, color: str) -> str:
        if not self.enabled:
            return text
        return f"{color}{text}{RESET}"

    def strong(self, text: str) -> str:
        return self.color(text, BOLD)

    def dim(self, text: str) -> str:
        return self.color(text, DIM)

def enable_windows_virtual_terminal() -> bool:
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        if handle in (0, -1):
            return False
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        enable_virtual_terminal_processing = 0x0004
        if mode.value & enable_virtual_terminal_processing:
            return True
        return bool(kernel32.SetConsoleMode(handle, mode.value | enable_virtual_terminal_processing))
    except Exception:
        return False

def configure_text_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

def should_use_color(force_color: bool, plain: bool) -> bool:
    if plain or os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty() and not force_color:
        return False
    return enable_windows_virtual_terminal()

def interactive_output() -> bool:
    return sys.stdout.isatty()

__all__ = [
    "RESET", "BOLD", "DIM", "FG_OK", "FG_WARN", "FG_FAIL", "FG_SKIP", "FG_TEXT", "FG_INFO", "FG_ACCENT",
    "HIDE_CURSOR", "SHOW_CURSOR", "CLEAR_LINE", "Palette", "enable_windows_virtual_terminal",
    "configure_text_output", "should_use_color", "interactive_output",
]
