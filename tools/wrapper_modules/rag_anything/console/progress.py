from __future__ import annotations

import threading
import time
from typing import Any

from wrapper_modules.rag_anything.checks.runner import Checker
from wrapper_modules.rag_anything.console.palette import CLEAR_LINE, FG_ACCENT, FG_INFO, FG_OK, HIDE_CURSOR, SHOW_CURSOR, Palette
from wrapper_modules.rag_anything.console.terminal import sleep_frame
from wrapper_modules.rag_anything.console.types import VisualItem
from wrapper_modules.rag_anything.core.models import STATUS_FAIL, STATUS_OK, STATUS_SKIP, STATUS_WARN

def progress_bar(value: int, total: int, width: int = 34) -> str:
    if total <= 0:
        total = 1
    ratio = max(0.0, min(1.0, value / total))
    filled = int(width * ratio)
    return "[" + "#" * filled + "-" * (width - filled) + f"] {int(ratio * 100):3d}%"

def readiness_bar(items: list[VisualItem], width: int = 20) -> tuple[str, str]:
    total = len(items) or 1
    ok = sum(1 for item in items if item.status == STATUS_OK)
    warn = sum(1 for item in items if item.status == STATUS_WARN)
    fail = sum(1 for item in items if item.status == STATUS_FAIL)
    skip = sum(1 for item in items if item.status == STATUS_SKIP)
    bar = progress_bar(ok, total, width=width)
    return bar, f"{ok}/{total} готово, {warn} огр., {fail} блок., {skip} не вкл."

def animated_boot(palette: Palette, enabled: bool) -> None:
    if not enabled:
        return
    stages = [
        "загружаю конфиг",
        "сканирую сабмодуль RAG-Anything",
        "сопоставляю парсеры и мультимодальные модули",
        "проверяю локальные зависимости",
        "собираю экран отчёта",
    ]
    print(HIDE_CURSOR if palette.enabled else "", end="", flush=True)
    try:
        for index, stage in enumerate(stages, 1):
            bar = progress_bar(index, len(stages))
            print(
                CLEAR_LINE
                + palette.color(":: ", FG_ACCENT)
                + palette.strong("rag-console")
                + " "
                + palette.color(bar, FG_INFO)
                + " "
                + stage,
                end="",
                flush=True,
            )
            sleep_frame(0.10)
        print(CLEAR_LINE, end="", flush=True)
    finally:
        print(SHOW_CURSOR if palette.enabled else "", end="", flush=True)

def run_checker_with_spinner(checker: Checker, palette: Palette, enabled: bool) -> Any:
    if not enabled:
        return checker.run()

    box: dict[str, Any] = {"report": None, "error": None}

    def worker() -> None:
        try:
            box["report"] = checker.run()
        except BaseException as exc:  # pragma: no cover - surfaced after spinner
            box["error"] = exc

    thread = threading.Thread(target=worker, daemon=True)
    frames = ["|", "/", "-", "\\"]
    thread.start()
    started = time.time()
    print(HIDE_CURSOR if palette.enabled else "", end="", flush=True)
    try:
        index = 0
        while thread.is_alive():
            elapsed = time.time() - started
            frame = frames[index % len(frames)]
            bar = progress_bar(min(int(elapsed * 10), 28), 28, width=28)
            print(
                CLEAR_LINE
                + palette.color(frame, FG_ACCENT)
                + " выполняю проверки "
                + palette.color(bar, FG_INFO)
                + f" {elapsed:4.1f}s",
                end="",
                flush=True,
            )
            index += 1
            thread.join(0.08)
        print(CLEAR_LINE, end="", flush=True)
    finally:
        print(SHOW_CURSOR if palette.enabled else "", end="", flush=True)

    if box["error"] is not None:
        raise box["error"]
    print(
        palette.color(":: ", FG_ACCENT)
        + palette.strong("проверки завершены")
        + palette.color(" [готово]", FG_OK)
    )
    return box["report"]

__all__ = ["progress_bar", "readiness_bar", "animated_boot", "run_checker_with_spinner"]
