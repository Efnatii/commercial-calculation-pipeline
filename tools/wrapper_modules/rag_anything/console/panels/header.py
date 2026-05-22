from __future__ import annotations

from typing import Any

from wrapper_modules.rag_anything.console.items import coverage_items, cli_items, format_items, parser_items, processor_items, provider_items, storage_items
from wrapper_modules.rag_anything.console.palette import FG_ACCENT, FG_FAIL, FG_OK, FG_SKIP, FG_WARN, Palette
from wrapper_modules.rag_anything.console.text import names_line, print_rule, print_wrapped, status_mark, wrap_text, worst_status
from wrapper_modules.rag_anything.core.models import STATUS_FAIL, STATUS_OK, STATUS_SKIP, STATUS_WARN

def print_header(report: Any, width: int, palette: Palette, details: bool = False) -> None:
    counts = report.counts()
    title = "RAG-ANYTHING: ГОТОВНОСТЬ МОДУЛЕЙ И ОКРУЖЕНИЯ"
    print()
    print(palette.color("=" * width, FG_ACCENT))
    print(palette.strong(title.center(width)))
    print(palette.color("=" * width, FG_ACCENT))
    if details:
        print(f"Проект  : {report.project_root}")
        print(f"RAG     : {report.rag_dir}")
        print(f"Конфиг  : {report.config_path}")
    print(
        "Итог    : "
        f"{palette.color('можно=' + str(counts.get(STATUS_OK, 0)), FG_OK)}  "
        f"{palette.color('ограничено=' + str(counts.get(STATUS_WARN, 0)), FG_WARN)}  "
        f"{palette.color('нельзя=' + str(counts.get(STATUS_FAIL, 0)), FG_FAIL)}  "
        f"{palette.color('не включено=' + str(counts.get(STATUS_SKIP, 0)), FG_SKIP)}"
    )
    discovered = report.discovered
    if details:
        print(
            "Состав  : "
            f"парсеры={len(discovered.get('parsers', {}).get('names', []))}, "
            f"модули={len(discovered.get('processors', {}))}, "
            f"доп. пакеты={len(discovered.get('pyproject', {}).get('optional_dependencies', {}))}, "
            f"env-ключи={len(discovered.get('env_surface', {}).get('all_keys', []))}, "
            f"экспорты={len(discovered.get('exports', {}).get('symbols', []))}"
        )
    else:
        print(
            "Модули  : "
            f"парсеры={len(parser_items(report))}, "
            f"мультимодальные={len(processor_items(report))}, "
            f"форматы={len(format_items(report))}, "
            f"CLI={len(cli_items(report))}"
        )
    print("Легенда : [+] можно  [!] ограничено  [x] нельзя  [-] не выбрано")
    reader_text = (
        "у каждого модуля есть назначение, проверка и действие для исправления. "
        "Если строка помечена [x], модуль сейчас не готов; [!] означает частичную готовность или необязательную зависимость."
    )
    reader_prefix = "Как читать: "
    reader_lines = wrap_text(reader_text, width - len(reader_prefix))
    print(reader_prefix + reader_lines[0])
    for line in reader_lines[1:]:
        print(" " * len(reader_prefix) + line)
    print()

def print_navigation(width: int, palette: Palette) -> None:
    links = [
        ("01", "Сводка готовности", "быстрый ответ, что готово и что заблокировано"),
        ("02", "Что видно сразу", "короткий список доступных и недоступных возможностей"),
        ("03", "Парсеры", "MinerU, Docling, PaddleOCR"),
        ("04", "Мультимодальные модули", "image, table, equation, generic"),
        ("05", "Форматы", "Office, Markdown, PDF renderer, изображения"),
        ("06", "LLM и эмбеддинги", "переменные и провайдеры для поиска и ответов"),
        ("07", "Хранилища и CLI", "хранилища и команды запуска"),
    ]
    print_rule("НАВИГАЦИЯ ПО ОТЧЁТУ", width, palette)
    for number, title, note in links:
        heading = f"  [{number}] {title}"
        print(palette.strong(heading))
        print_wrapped(note, width, indent="       ", palette=palette, dim=True)
    print()

def print_verdict(report: Any, width: int, palette: Palette) -> None:
    parser_failures = [item for item in parser_items(report) if item.status == STATUS_FAIL]
    parser_warnings = [item for item in parser_items(report) if item.status == STATUS_WARN]
    provider_failures = [item for item in provider_items(report) if item.status == STATUS_FAIL]
    format_warnings = [item for item in format_items(report) if item.status == STATUS_WARN]
    storage_skips = [item for item in storage_items(report) if item.status == STATUS_SKIP]
    coverage_status = worst_status([item.status for item in coverage_items(report)])

    print_rule("ИТОГОВЫЙ ВЫВОД", width, palette)
    print(f"  {status_mark(coverage_status, palette)} {palette.strong('обвязка RAG покрывает текущий submodule')}")
    if coverage_status == STATUS_OK:
        print_wrapped("Конфиг видит все найденные парсеры, модули, env-ключи, CLI-аргументы, API и экспорты.", width, indent="      ")
    else:
        print_wrapped("В покрытии есть разрыв: upstream RAG-Anything изменился, конфиг нужно обновить.", width, indent="      ")

    if parser_failures or parser_warnings:
        names = names_line(parser_failures + parser_warnings)
        print(f"  {status_mark(STATUS_FAIL if parser_failures else STATUS_WARN, palette)} {palette.strong('парсинг документов пока не полный')}")
        print_wrapped(f"Проблемные парсеры и исполняемые зависимости: {names}. Без них часть PDF, сканов или Office-файлов не будет разбираться.", width, indent="      ")

    if provider_failures:
        print(f"  {status_mark(STATUS_FAIL, palette)} {palette.strong('RAG-поиск и ответы ещё не настроены')}")
        print_wrapped(
            "Не заданы переменные LLM и эмбеддингов. Парсинг можно проверять отдельно, но полноценный поиск и генерация ответов не стартуют.",
            width,
            indent="      ",
        )

    if format_warnings:
        print(f"  {status_mark(STATUS_WARN, palette)} {palette.strong('часть форматов требует дополнительных пакетов')}")
        print_wrapped(f"Ограничены: {names_line(format_warnings)}.", width, indent="      ")

    if storage_skips:
        print(f"  {status_mark(STATUS_SKIP, palette)} {palette.strong('хранилища выключены намеренно')}")
        print_wrapped("Это не ошибка: PostgreSQL, Neo4j, Qdrant, Redis и другие хранилища нужны только если выбраны через LIGHTRAG_*.", width, indent="      ")
    print()

__all__ = ["print_header", "print_navigation", "print_verdict"]
