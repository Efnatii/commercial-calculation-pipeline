from __future__ import annotations

from typing import Any

from wrapper_modules.rag_anything.console.palette import FG_ACCENT, Palette, configure_text_output, interactive_output, should_use_color
from wrapper_modules.rag_anything.console.panels import (
    print_header,
)
from wrapper_modules.rag_anything.console.progress import animated_boot, run_checker_with_spinner
from wrapper_modules.rag_anything.console.terminal import project_root, terminal_width
from wrapper_modules.rag_anything.console.text import print_wrapped
from wrapper_modules.rag_anything.plugins.registry import get_console_panel_plugins


def print_visual_report(report: Any, palette: Palette, details: bool = False) -> None:
    width = terminal_width()
    print_header(report, width, palette, details=details)
    context = {"width": width, "palette": palette}
    for plugin in get_console_panel_plugins(details=details):
        plugin.render(report, context)
    if not details:
        print_wrapped(
            "Подробные служебные списки API/env/exports скрыты. Для полного диагностического отчета запусти с -Details.",
            width,
            indent="  ",
            palette=palette,
            dim=True,
        )
    print(palette.color("=" * width, FG_ACCENT))
    print()


__all__ = [
    "Palette", "configure_text_output", "interactive_output", "should_use_color", "animated_boot",
    "run_checker_with_spinner", "project_root", "print_visual_report",
]
