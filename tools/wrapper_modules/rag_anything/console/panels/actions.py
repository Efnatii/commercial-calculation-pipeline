from __future__ import annotations

from typing import Any

from wrapper_modules.rag_anything.console.catalog import GROUP_NOTES
from wrapper_modules.rag_anything.console.items import (
    cli_items,
    coverage_items,
    format_items,
    parser_items,
    processor_items,
    provider_items,
    smoke_items,
    storage_items,
)
from wrapper_modules.rag_anything.console.palette import FG_INFO, Palette
from wrapper_modules.rag_anything.console.progress import readiness_bar
from wrapper_modules.rag_anything.console.text import (
    names_line,
    print_field,
    print_named_list,
    print_rule,
    print_wrapped,
    status_label,
    status_mark,
    translate_detail,
    worst_status,
)
from wrapper_modules.rag_anything.core.models import STATUS_FAIL, STATUS_OK, STATUS_SKIP, STATUS_WARN

def print_decision_board(report: Any, width: int, palette: Palette) -> None:
    groups = [
        ("Покрытие обвязки", coverage_items(report)),
        ("Парсеры", parser_items(report)),
        ("Мультимодальные модули", processor_items(report)),
        ("Форматы и конвертеры", format_items(report)),
        ("LLM и эмбеддинги", provider_items(report)),
        ("Хранилища", storage_items(report)),
        ("CLI инструменты", cli_items(report)),
        ("Реальные smoke-пробы", smoke_items(report)),
    ]
    print_rule("СВОДКА ГОТОВНОСТИ", width, palette)
    for title, items in groups:
        status = worst_status([item.status for item in items])
        usable = {
            STATUS_OK: "готово к работе",
            STATUS_WARN: "можно частично",
            STATUS_FAIL: "заблокировано",
            STATUS_SKIP: "не настроено",
        }.get(status, "unknown")
        bar, summary = readiness_bar(items, width=18)
        print(f"  {status_mark(status, palette)} {palette.strong(title)} - {status_label(status, palette)}")
        print(f"      готовность: {palette.color(bar, FG_INFO)}  {usable}; {summary}")
        note = GROUP_NOTES.get(title)
        if note:
            print_wrapped(note, width, indent="      ", palette=palette, dim=True)
    print()

def print_now_available(report: Any, width: int, palette: Palette) -> None:
    print_rule("ЧТО ВИДНО СРАЗУ", width, palette)
    available_groups = [
        ("мультимодальные модули", [item for item in processor_items(report) if item.status == STATUS_OK]),
        ("форматы/конвертеры", [item for item in format_items(report) if item.status == STATUS_OK]),
        ("CLI-команды", [item for item in cli_items(report) if item.status == STATUS_OK]),
        ("покрытие обвязки", [item for item in coverage_items(report) if item.status == STATUS_OK]),
    ]
    blocked_groups = [
        ("парсеры", [item for item in parser_items(report) if item.status == STATUS_FAIL]),
        ("LLM и эмбеддинги", [item for item in provider_items(report) if item.status == STATUS_FAIL]),
        ("форматы/конвертеры", [item for item in format_items(report) if item.status == STATUS_FAIL]),
        ("runtime smoke", [item for item in smoke_items(report) if item.status == STATUS_FAIL]),
    ]
    limited_groups = [
        ("парсеры", [item for item in parser_items(report) if item.status == STATUS_WARN]),
        ("форматы/конвертеры", [item for item in format_items(report) if item.status == STATUS_WARN]),
        ("CLI-команды", [item for item in cli_items(report) if item.status == STATUS_WARN]),
    ]

    print(f"  {status_mark(STATUS_OK, palette)} {palette.strong('можно использовать сейчас')}")
    for title, items in available_groups:
        if items:
            if title == "покрытие обвязки":
                print_named_list(title, f"все проверки покрытия прошли ({len(items)}).", width)
            else:
                print_named_list(title, names_line(items), width)

    print(f"  {status_mark(STATUS_FAIL, palette)} {palette.strong('нельзя использовать до настройки')}")
    any_blocked = False
    for title, items in blocked_groups:
        if items:
            any_blocked = True
            print_named_list(title, names_line(items), width)
    if not any_blocked:
        print_wrapped("критических блокировок нет", width, indent="      ")

    print(f"  {status_mark(STATUS_WARN, palette)} {palette.strong('есть, но с ограничениями')}")
    any_limited = False
    for title, items in limited_groups:
        if items:
            any_limited = True
            print_named_list(title, names_line(items), width)
    if not any_limited:
        print_wrapped("ограничений нет", width, indent="      ")

    print_wrapped(
        "Ниже только действия, которые реально меняют готовность. Полная техническая расшифровка доступна через -Details.",
        width,
        indent="  ",
        palette=palette,
        dim=True,
    )
    print()

def print_help_lines(report: Any, width: int, palette: Palette) -> None:
    print_rule("ЧТО ИСПРАВИТЬ В ПЕРВУЮ ОЧЕРЕДЬ", width, palette)
    actions: list[tuple[str, str, str]] = []

    mineru = next((item for item in parser_items(report) if item.name == "mineru" and item.status == STATUS_FAIL), None)
    if mineru:
        actions.append((STATUS_FAIL, "MinerU: основной парсер PDF/сканов", translate_detail(mineru.reason or mineru.detail)))

    provider_failures = [item for item in provider_items(report) if item.status == STATUS_FAIL]
    if provider_failures:
        names = names_line(provider_failures)
        actions.append((STATUS_FAIL, "LLM и эмбеддинги: поиск и ответы", f"Задать в .env: {names}."))

    smoke_failure = next((item for item in smoke_items(report) if item.status == STATUS_FAIL), None)
    if smoke_failure:
        actions.append((STATUS_FAIL, "Runtime smoke: реальный импорт и запуск RAG", translate_detail(smoke_failure.reason or smoke_failure.detail)))

    docling = next((item for item in parser_items(report) if item.name == "docling" and item.status == STATUS_WARN), None)
    if docling:
        actions.append((STATUS_WARN, "Docling: альтернативный парсер Office/HTML/PDF", translate_detail(docling.reason or docling.detail)))

    paddleocr = next((item for item in parser_items(report) if item.name == "paddleocr" and item.status == STATUS_WARN), None)
    paddle_runtime = next((item for item in format_items(report) if item.name == "paddle runtime" and item.status == STATUS_WARN), None)
    if paddleocr or paddle_runtime:
        reason = translate_detail((paddleocr or paddle_runtime).reason or (paddleocr or paddle_runtime).detail)
        actions.append((STATUS_WARN, "PaddleOCR: OCR для сканов", reason))

    office = next((item for item in format_items(report) if item.name == "office: DOC/PPT/XLS" and item.status == STATUS_WARN), None)
    if office:
        actions.append((STATUS_WARN, "LibreOffice: DOC/PPT/XLS конвертация", translate_detail(office.reason or office.detail)))

    markdown_missing = [item for item in format_items(report) if item.name in {"markdown package", "markdown PDF engine"} and item.status == STATUS_WARN]
    if markdown_missing:
        actions.append((STATUS_WARN, "Пакеты Markdown: Markdown -> PDF", "Установить: pip install 'raganything[markdown]'"))

    pandoc = next((item for item in cli_items(report) if item.name == "optional_tool:pandoc" and item.status == STATUS_WARN), None)
    if pandoc:
        actions.append((STATUS_WARN, "Pandoc: только для pandoc-режима", translate_detail(pandoc.reason or pandoc.detail)))

    if not actions:
        print(f"  {status_mark(STATUS_OK, palette)} Все проверенные runtime-модули можно использовать.")
        print()
        return

    for index, (status, title, action) in enumerate(actions, 1):
        print(f"  {status_mark(status, palette)} [{index}] {palette.strong(title)}")
        print_field("действие", action, width, palette)
    print()

__all__ = ["print_decision_board", "print_now_available", "print_help_lines"]
