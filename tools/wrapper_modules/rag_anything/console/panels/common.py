from __future__ import annotations

from wrapper_modules.rag_anything.console.catalog import SECTION_NOTES
from wrapper_modules.rag_anything.console.items import status_counts
from wrapper_modules.rag_anything.console.palette import FG_FAIL, FG_OK, FG_SKIP, FG_WARN, Palette, RESET
from wrapper_modules.rag_anything.console.text import (
    print_field,
    print_named_list,
    print_rule,
    print_wrapped,
    status_label,
    status_mark,
    strip_ansi,
    translate_detail,
    worst_status,
)
from wrapper_modules.rag_anything.console.types import VisualItem
from wrapper_modules.rag_anything.core.models import STATUS_FAIL, STATUS_OK, STATUS_SKIP, STATUS_WARN

def print_section(title: str, items: list[VisualItem], width: int, palette: Palette, limit: int | None = None) -> None:
    print_rule(title, width, palette)
    if title in SECTION_NOTES:
        print_wrapped(SECTION_NOTES[title], width, indent="  ", palette=palette, dim=True)
    if not items:
        print(f"  {status_mark(STATUS_SKIP, palette)} нет элементов")
        print()
        return
    visible = items if limit is None else items[:limit]
    for item in visible:
        mark = status_mark(item.status, palette)
        state = status_label(item.status, palette)
        print(f"  {mark} {palette.strong(item.name)} - {state}")
        if item.note:
            print_field("что это", item.note, width, palette)
        elif item.detail:
            print_field("проверка", translate_detail(item.detail), width, palette)
        if item.note and item.detail:
            print_field("проверка", translate_detail(item.detail), width, palette)
        if item.status in {STATUS_FAIL, STATUS_WARN} and item.reason:
            print_field("исправить", translate_detail(item.reason), width, palette)
        print()
    if limit is not None and len(items) > limit:
        print_wrapped(f"Ещё {len(items) - limit} строк скрыто в кратком режиме этого раздела.", width, indent="      ", palette=palette, dim=True)
    print()

def visual_ratio_bar(items: list[VisualItem], palette: Palette, width: int = 28) -> str:
    ok, warn, fail, skip = status_counts(items)
    total = max(1, ok + warn + fail + skip)
    segments = [
        (STATUS_OK, ok, "#", FG_OK),
        (STATUS_WARN, warn, "!", FG_WARN),
        (STATUS_FAIL, fail, "x", FG_FAIL),
        (STATUS_SKIP, skip, "-", FG_SKIP),
    ]
    chunks: list[str] = []
    used = 0
    for index, (status, count, char, color) in enumerate(segments):
        if count <= 0:
            continue
        if index == len(segments) - 1:
            size = max(1, width - used)
        else:
            size = max(1, round(width * count / total))
        used += size
        chunks.append(palette.color(char * size, color))
    plain_len = sum(len(chunk.replace(RESET, "").replace(FG_OK, "").replace(FG_WARN, "").replace(FG_FAIL, "").replace(FG_SKIP, "")) for chunk in chunks)
    if plain_len < width:
        chunks.append("-" * (width - plain_len))
    return "[" + "".join(chunks) + "]"

def compact_chips(items: list[VisualItem], palette: Palette, width: int, indent: str = "      ") -> None:
    line = indent
    for item in items:
        chip = f"{status_mark(item.status, palette)} {item.name}"
        plain_chip = f"{status_mark(item.status, Palette(False))} {item.name}"
        if len(strip_ansi(line)) + len(plain_chip) + 3 > width and line.strip():
            print(line.rstrip())
            line = indent + chip + "   "
        else:
            line += chip + "   "
    if line.strip():
        print(line.rstrip())

def print_category_card(
    title: str,
    items: list[VisualItem],
    meaning: str,
    settings: str,
    width: int,
    palette: Palette,
    extra: str = "",
    settings_label: str = "настройки",
) -> None:
    state = worst_status([item.status for item in items])
    print(f"  {status_mark(state, palette)} {palette.strong(title)} - {status_label(state, palette)}")
    print_wrapped(meaning, width, indent="      ")
    if items:
        print("      состав:")
        compact_chips(items, palette, width, indent="        ")
    if settings:
        print_named_list(settings_label, settings, width)
    if extra:
        print_named_list("важно", extra, width)
    print()

__all__ = ["print_section", "visual_ratio_bar", "compact_chips", "print_category_card"]
