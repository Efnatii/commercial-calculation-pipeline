from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from wrapper_modules.rag_anything.checks.plugins import BUILTIN_CHECK_PLUGINS, BuiltinCheckPlugin

ConsoleRenderer = Callable[[Any, dict[str, Any]], None]


@dataclass(frozen=True)
class BuiltinConsolePanelPlugin:
    id: str
    title: str
    renderer: ConsoleRenderer

    def render(self, report: Any, context: Any) -> list[str]:
        self.renderer(report, dict(context))
        return []


@dataclass(frozen=True)
class BuiltinCommandPlugin:
    name: str
    title: str

    def add_arguments(self, parser: Any) -> None:
        return None

    def run(self, args: Any) -> int:
        raise NotImplementedError(self.name)


def _width(context: dict[str, Any]) -> int:
    return int(context["width"])


def _palette(context: dict[str, Any]) -> Any:
    return context["palette"]


def _readiness(report: Any, context: dict[str, Any]) -> None:
    from wrapper_modules.rag_anything.console.panels import print_decision_board

    print_decision_board(report, _width(context), _palette(context))


def _pipeline_map(report: Any, context: dict[str, Any]) -> None:
    from wrapper_modules.rag_anything.console.panels import print_pipeline_map

    print_pipeline_map(report, _width(context), _palette(context))


def _module_map(report: Any, context: dict[str, Any]) -> None:
    from wrapper_modules.rag_anything.console.panels import print_module_map

    print_module_map(report, _width(context), _palette(context))


def _category_breakdown(report: Any, context: dict[str, Any]) -> None:
    from wrapper_modules.rag_anything.console.panels import print_category_breakdown

    print_category_breakdown(report, _width(context), _palette(context))


def _availability(report: Any, context: dict[str, Any]) -> None:
    from wrapper_modules.rag_anything.console.panels import print_now_available

    print_now_available(report, _width(context), _palette(context))


def _fix_first(report: Any, context: dict[str, Any]) -> None:
    from wrapper_modules.rag_anything.console.panels import print_help_lines

    print_help_lines(report, _width(context), _palette(context))


def _navigation(report: Any, context: dict[str, Any]) -> None:
    from wrapper_modules.rag_anything.console.panels import print_navigation

    print_navigation(_width(context), _palette(context))


def _section(title: str, item_getter: Callable[[Any], list[Any]], limit: int | None = None) -> ConsoleRenderer:
    def render(report: Any, context: dict[str, Any]) -> None:
        from wrapper_modules.rag_anything.console.panels import print_section

        print_section(title, item_getter(report), _width(context), _palette(context), limit=limit)

    return render


def _parser_items(report: Any) -> list[Any]:
    from wrapper_modules.rag_anything.console.items import parser_items

    return parser_items(report)


def _processor_items(report: Any) -> list[Any]:
    from wrapper_modules.rag_anything.console.items import processor_items

    return processor_items(report)


def _format_items(report: Any) -> list[Any]:
    from wrapper_modules.rag_anything.console.items import format_items

    return format_items(report)


def _provider_items(report: Any) -> list[Any]:
    from wrapper_modules.rag_anything.console.items import provider_items

    return provider_items(report)


def _storage_items(report: Any) -> list[Any]:
    from wrapper_modules.rag_anything.console.items import storage_items

    return storage_items(report)


def _cli_items(report: Any) -> list[Any]:
    from wrapper_modules.rag_anything.console.items import cli_items

    return cli_items(report)


def _coverage_items(report: Any) -> list[Any]:
    from wrapper_modules.rag_anything.console.items import coverage_items

    return coverage_items(report)


def _smoke_items(report: Any) -> list[Any]:
    from wrapper_modules.rag_anything.console.items import smoke_items

    return smoke_items(report)


def _env_group_items(report: Any) -> list[Any]:
    from wrapper_modules.rag_anything.console.items import env_group_items

    return env_group_items(report)


BUILTIN_DEFAULT_CONSOLE_PANELS: tuple[BuiltinConsolePanelPlugin, ...] = (
    BuiltinConsolePanelPlugin("readiness", "Readiness summary", _readiness),
    BuiltinConsolePanelPlugin("pipeline_map", "Pipeline map", _pipeline_map),
    BuiltinConsolePanelPlugin("module_map", "Module map", _module_map),
    BuiltinConsolePanelPlugin("category_breakdown", "Category breakdown", _category_breakdown),
    BuiltinConsolePanelPlugin("availability", "Availability summary", _availability),
    BuiltinConsolePanelPlugin("fix_first", "Priority fixes", _fix_first),
)

BUILTIN_DETAIL_CONSOLE_PANELS: tuple[BuiltinConsolePanelPlugin, ...] = (
    BuiltinConsolePanelPlugin("navigation", "Navigation", _navigation),
    BuiltinConsolePanelPlugin(
        "parsers_detail",
        "Parser details",
        _section("ПАРСЕРЫ, КОТОРЫЕ ДАЕТ RAG", _parser_items),
    ),
    BuiltinConsolePanelPlugin(
        "processors_detail",
        "Processor details",
        _section("МУЛЬТИМОДАЛЬНЫЕ МОДУЛИ", _processor_items),
    ),
    BuiltinConsolePanelPlugin(
        "formats_detail",
        "Format details",
        _section("ФОРМАТЫ И КОНВЕРТЕРЫ", _format_items),
    ),
    BuiltinConsolePanelPlugin(
        "providers_detail",
        "Provider details",
        _section("LLM И ЭМБЕДДИНГИ", _provider_items),
    ),
    BuiltinConsolePanelPlugin("storage_detail", "Storage details", _section("ХРАНИЛИЩА", _storage_items)),
    BuiltinConsolePanelPlugin("cli_detail", "CLI details", _section("CLI-ПОВЕРХНОСТЬ", _cli_items)),
    BuiltinConsolePanelPlugin(
        "coverage_detail",
        "Coverage/API/export details",
        _section("ПОКРЫТИЕ, API И ЭКСПОРТЫ", _coverage_items, limit=18),
    ),
    BuiltinConsolePanelPlugin(
        "smoke_detail",
        "Real runtime smoke checks",
        _section("РЕАЛЬНЫЕ SMOKE-ПРОВЕРКИ", _smoke_items, limit=24),
    ),
    BuiltinConsolePanelPlugin(
        "env_groups_detail",
        "Config groups",
        _section("ГРУППЫ КОНФИГА", _env_group_items, limit=30),
    ),
)

DEFAULT_CONSOLE_PANEL_IDS: tuple[str, ...] = tuple(plugin.id for plugin in BUILTIN_DEFAULT_CONSOLE_PANELS)

DETAIL_CONSOLE_PANEL_IDS: tuple[str, ...] = tuple(plugin.id for plugin in BUILTIN_DETAIL_CONSOLE_PANELS)

BUILTIN_CONSOLE_PANELS: tuple[BuiltinConsolePanelPlugin, ...] = (
    BUILTIN_DEFAULT_CONSOLE_PANELS + BUILTIN_DETAIL_CONSOLE_PANELS
)

BUILTIN_COMMANDS: tuple[BuiltinCommandPlugin, ...] = (
    BuiltinCommandPlugin("check", "Plain RAG wrapper checker"),
    BuiltinCommandPlugin("visual", "Visual RAG wrapper dashboard"),
)


def get_check_plugins() -> tuple[BuiltinCheckPlugin, ...]:
    return BUILTIN_CHECK_PLUGINS


def get_console_panel_plugins(details: bool = False) -> tuple[BuiltinConsolePanelPlugin, ...]:
    ids = DEFAULT_CONSOLE_PANEL_IDS + (DETAIL_CONSOLE_PANEL_IDS if details else ())
    by_id = {plugin.id: plugin for plugin in BUILTIN_CONSOLE_PANELS}
    return tuple(by_id[panel_id] for panel_id in ids)


def get_console_panel_order(details: bool = False) -> tuple[str, ...]:
    return tuple(plugin.id for plugin in get_console_panel_plugins(details=details))


def get_command_plugins() -> tuple[BuiltinCommandPlugin, ...]:
    return BUILTIN_COMMANDS


__all__ = [
    "BuiltinConsolePanelPlugin",
    "BuiltinCommandPlugin",
    "BUILTIN_DEFAULT_CONSOLE_PANELS",
    "BUILTIN_DETAIL_CONSOLE_PANELS",
    "DEFAULT_CONSOLE_PANEL_IDS",
    "DETAIL_CONSOLE_PANEL_IDS",
    "BUILTIN_CONSOLE_PANELS",
    "BUILTIN_COMMANDS",
    "get_check_plugins",
    "get_console_panel_plugins",
    "get_console_panel_order",
    "get_command_plugins",
]
