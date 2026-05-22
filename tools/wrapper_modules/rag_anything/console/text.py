from __future__ import annotations

import re
import textwrap

from wrapper_modules.rag_anything.console.palette import FG_ACCENT, FG_FAIL, FG_OK, FG_SKIP, FG_WARN, Palette, RESET
from wrapper_modules.rag_anything.console.types import VisualItem
from wrapper_modules.rag_anything.core.models import STATUS_FAIL, STATUS_OK, STATUS_SKIP, STATUS_WARN

def strip_line(text: str) -> str:
    return " ".join(str(text).replace("\r", " ").replace("\n", " ").split())

def fit(text: str, width: int) -> str:
    text = strip_line(text)
    if len(text) <= width:
        return text
    return text[: max(0, width - 3)] + "..."

def wrap_text(text: str, width: int) -> list[str]:
    text = strip_line(text)
    if not text:
        return [""]
    return textwrap.wrap(
        text,
        width=max(20, width),
        break_long_words=False,
        break_on_hyphens=False,
        replace_whitespace=True,
    ) or [text]

def print_wrapped(text: str, width: int, indent: str = "  ", palette: Palette | None = None, dim: bool = False) -> None:
    for line in wrap_text(text, width - len(indent)):
        if palette and dim:
            line = palette.dim(line)
        print(indent + line)

def print_field(label: str, value: str, width: int, palette: Palette, indent: str = "      ") -> None:
    value = strip_line(value)
    if not value:
        return
    prefix = f"{indent}{label:<10}: "
    continuation = " " * len(prefix)
    lines = wrap_text(value, width - len(prefix))
    print(prefix + lines[0])
    for line in lines[1:]:
        print(continuation + line)

def names_line(items: list[VisualItem]) -> str:
    return ", ".join(item.name for item in items)

def print_named_list(label: str, value: str, width: int) -> None:
    prefix = f"      {label}: "
    continuation = " " * len(prefix)
    lines = wrap_text(value, width - len(prefix))
    print(prefix + lines[0])
    for line in lines[1:]:
        print(continuation + line)

def translate_detail(text: str) -> str:
    text = strip_line(text)
    exact = {
        "Pillow import works": "Pillow импортируется.",
        "reportlab import works": "ReportLab импортируется.",
        "pygments import works": "Pygments импортируется.",
        "pypdfium2 import works": "pypdfium2 импортируется.",
        "LibreOffice/soffice not found": "LibreOffice/soffice не найден.",
        "Required env var is not set": "Обязательная env-переменная не задана.",
        "Not selected/configured": "Не выбрано в env/config.",
        "All discovered parsers are listed": "Все обнаруженные парсеры учтены.",
        "All discovered processors are listed": "Все мультимодальные модули учтены.",
        "All optional extras are listed": "Все дополнительные зависимости учтены.",
        "All package exports are listed": "Все экспорты пакета учтены.",
        "All symbols discovered": "Все символы найдены.",
        "Install LibreOffice and ensure libreoffice or soffice is on PATH.": "Установить LibreOffice и добавить libreoffice/soffice в PATH.",
        "Install pandoc if you need this CLI method.": "Установить Pandoc, если нужен этот CLI-режим.",
    }
    if text in exact:
        return exact[text]
    if text.startswith("Command not found: "):
        return "Команда не найдена: " + text.split(": ", 1)[1]
    if text.startswith("ModuleNotFoundError: No module named "):
        return "Python-модуль не найден: " + text.rsplit(" ", 1)[1]
    if text.startswith("EquationModalProcessor:"):
        return "Модуль формул найден: разбирает формулы, переменные и смысл математических выражений."
    if text.startswith("GenericModalProcessor:"):
        return "Общий мультимодальный модуль найден: анализирует нестандартный контент и извлекает сущности."
    if text.startswith("ImageModalProcessor:"):
        return "Модуль изображений найден: описывает изображения, понимает визуальный контент и извлекает сущности."
    if text.startswith("TableModalProcessor:"):
        return "Модуль таблиц найден: анализирует структуру таблиц, статистику, тренды и табличные сущности."
    if text.startswith("Install with: "):
        command = text.split(": ", 1)[1].replace(", then install paddlepaddle.", ", затем установить paddlepaddle.")
        return "Установить: " + command
    if text.startswith("Install PaddlePaddle from "):
        return "Установить PaddlePaddle: " + text.removeprefix("Install PaddlePaddle from ")
    match = re.fullmatch(r"Set ([A-Z0-9_]+) in \.env or remove it from policy\.required_env\.", text)
    if match:
        return f"Задать {match.group(1)} в .env или убрать из policy.required_env."
    match = re.fullmatch(r"All (\d+) discovered env keys are grouped", text)
    if match:
        return f"Все найденные env-ключи разложены по группам: {match.group(1)}."
    match = re.fullmatch(r"All (\d+) CLI args are listed", text)
    if match:
        return f"Все CLI-аргументы учтены: {match.group(1)}."
    match = re.fullmatch(r"All (\d+) public methods are listed", text)
    if match:
        return f"Все публичные методы API учтены: {match.group(1)}."
    match = re.fullmatch(r"(\d+)/(\d+) configured method\(s\) discovered", text)
    if match:
        return f"Найдено методов: {match.group(1)}/{match.group(2)}."
    match = re.fullmatch(r"(\d+)/(\d+) keys set(?: - .*)?", text)
    if match:
        return f"Задано env-ключей: {match.group(1)}/{match.group(2)}."
    match = re.fullmatch(r"raganything\.([A-Za-z0-9_]+) exposes (\d+) argument\(s\)", text)
    if match:
        return f"raganything.{match.group(1)}: найдено CLI-аргументов: {match.group(2)}."
    match = re.fullmatch(r"enabled=([^;]+); disabled=(\d+)", text)
    if match:
        return f"Включено: {match.group(1)}; выключено быстрых проверок: {match.group(2)}."
    return text

def status_rank(status: str) -> int:
    return {STATUS_FAIL: 0, STATUS_WARN: 1, STATUS_SKIP: 2, STATUS_OK: 3}.get(status, 1)

def worst_status(statuses: list[str]) -> str:
    if not statuses:
        return STATUS_SKIP
    return min(statuses, key=status_rank)

def status_label(status: str, palette: Palette, width: int = 0) -> str:
    labels = {
        STATUS_OK: ("МОЖНО", FG_OK),
        STATUS_WARN: ("ОГРАНИЧЕНО", FG_WARN),
        STATUS_FAIL: ("НЕЛЬЗЯ", FG_FAIL),
        STATUS_SKIP: ("НЕ ВКЛЮЧЕНО", FG_SKIP),
    }
    label, color = labels.get(status, ("UNKNOWN", FG_WARN))
    if width:
        label = f"{label:<{width}}"
    return palette.color(label, color)

def status_mark(status: str, palette: Palette) -> str:
    marks = {
        STATUS_OK: ("[+]", FG_OK),
        STATUS_WARN: ("[!]", FG_WARN),
        STATUS_FAIL: ("[x]", FG_FAIL),
        STATUS_SKIP: ("[-]", FG_SKIP),
    }
    mark, color = marks.get(status, ("[?]", FG_WARN))
    return palette.color(mark, color)

def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", text)

def print_rule(title: str, width: int, palette: Palette) -> None:
    left = f" -- {title} "
    fill = max(0, width - len(left))
    print(palette.color(left, FG_ACCENT) + palette.dim("-" * fill))

__all__ = [
    "strip_line", "fit", "wrap_text", "print_wrapped", "print_field", "names_line", "print_named_list",
    "translate_detail", "status_rank", "worst_status", "status_label", "status_mark", "strip_ansi", "print_rule",
]
