from __future__ import annotations

from typing import Any

from wrapper_modules.rag_anything.console.items import group_rows, parser_items, processor_items, provider_items, status_counts, storage_items
from wrapper_modules.rag_anything.console.palette import Palette
from wrapper_modules.rag_anything.console.panels.common import compact_chips, visual_ratio_bar
from wrapper_modules.rag_anything.console.text import print_rule, status_label, status_mark, worst_status
from wrapper_modules.rag_anything.core.models import STATUS_OK

def print_pipeline_map(report: Any, width: int, palette: Palette) -> None:
    stages = [
        ("1", "Документы", STATUS_OK, "PDF / Office / Markdown / картинки"),
        ("2", "Парсеры", worst_status([item.status for item in parser_items(report)]), "MinerU, Docling, PaddleOCR"),
        ("3", "Мультимодальность", worst_status([item.status for item in processor_items(report)]), "image, table, equation, generic"),
        ("4", "LLM + поиск", worst_status([item.status for item in provider_items(report)]), "LLM и эмбеддинги"),
        ("5", "Хранилища", worst_status([item.status for item in storage_items(report)]), "опционально"),
    ]
    print_rule("ВИЗУАЛЬНАЯ КАРТА ПАЙПЛАЙНА", width, palette)
    line = "  "
    for index, (number, name, status, _) in enumerate(stages):
        piece = f"{status_mark(status, palette)} [{number}] {name}"
        if index:
            line += palette.dim("  ->  ")
        line += piece
    print(line)
    for _, name, status, note in stages:
        print(f"      {status_mark(status, palette)} {name:<18} {status_label(status, palette):<14} {note}")
    print()

def print_module_map(report: Any, width: int, palette: Palette) -> None:
    print_rule("КАРТА МОДУЛЕЙ", width, palette)
    for title, items in group_rows(report):
        ok, warn, fail, skip = status_counts(items)
        state = worst_status([item.status for item in items])
        print(f"  {status_mark(state, palette)} {palette.strong(title)}")
        print(f"      {visual_ratio_bar(items, palette, width=30)}  можно {ok}, ограничено {warn}, нельзя {fail}, не выбрано {skip}")
        compact_chips(items, palette, width)
    print()

__all__ = ["print_pipeline_map", "print_module_map"]
