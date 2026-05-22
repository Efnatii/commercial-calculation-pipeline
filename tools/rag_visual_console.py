#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rag_tool_check import (
    STATUS_FAIL,
    STATUS_OK,
    STATUS_SKIP,
    STATUS_WARN,
    Checker,
    as_list,
    load_config,
    resolve_path,
)


RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
FG_OK = "\033[32m"
FG_WARN = "\033[33m"
FG_FAIL = "\033[31m"
FG_SKIP = "\033[36m"
FG_TEXT = "\033[37m"


@dataclass
class VisualItem:
    name: str
    status: str
    detail: str
    reason: str = ""


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


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def terminal_width(default: int = 118) -> int:
    try:
        return max(90, min(150, os.get_terminal_size().columns))
    except OSError:
        return default


def strip_line(text: str) -> str:
    return " ".join(str(text).replace("\r", " ").replace("\n", " ").split())


def fit(text: str, width: int) -> str:
    text = strip_line(text)
    if len(text) <= width:
        return text
    return text[: max(0, width - 3)] + "..."


def status_rank(status: str) -> int:
    return {STATUS_FAIL: 0, STATUS_WARN: 1, STATUS_SKIP: 2, STATUS_OK: 3}.get(status, 1)


def worst_status(statuses: list[str]) -> str:
    if not statuses:
        return STATUS_SKIP
    return min(statuses, key=status_rank)


def status_label(status: str, palette: Palette, width: int = 0) -> str:
    labels = {
        STATUS_OK: ("CAN USE", FG_OK),
        STATUS_WARN: ("LIMITED", FG_WARN),
        STATUS_FAIL: ("BLOCKED", FG_FAIL),
        STATUS_SKIP: ("IDLE", FG_SKIP),
    }
    label, color = labels.get(status, ("UNKNOWN", FG_WARN))
    if width:
        label = f"{label:<{width}}"
    return palette.color(label, color)


def status_mark(status: str, palette: Palette) -> str:
    marks = {
        STATUS_OK: ("[OK]", FG_OK),
        STATUS_WARN: ("[!]", FG_WARN),
        STATUS_FAIL: ("[X]", FG_FAIL),
        STATUS_SKIP: ("[-]", FG_SKIP),
    }
    mark, color = marks.get(status, ("[?]", FG_WARN))
    return palette.color(mark, color)


def result_map(report: Any) -> dict[tuple[str, str], Any]:
    return {(result.category, result.name): result for result in report.results}


def results_by_category(report: Any, category: str) -> list[Any]:
    return [result for result in report.results if result.category == category]


def find_result(report: Any, category: str, name: str) -> Any | None:
    for result in report.results:
        if result.category == category and result.name == name:
            return result
    return None


def env_group_items(report: Any) -> list[VisualItem]:
    items: list[VisualItem] = []
    for result in results_by_category(report, "config"):
        if not result.name.startswith("env_group:"):
            continue
        name = result.name.split(":", 1)[1]
        items.append(VisualItem(name=name, status=result.status, detail=result.detail))
    return items


def parser_items(report: Any) -> list[VisualItem]:
    discovered = report.discovered.get("parsers", {}).get("names", [])
    items: list[VisualItem] = []
    for name in discovered:
        result = find_result(report, "parser", str(name))
        if result is None:
            items.append(VisualItem(str(name), STATUS_SKIP, "offered by RAG-Anything, not checked"))
        else:
            items.append(VisualItem(str(name), result.status, result.detail, result.remediation))
    return items


def processor_items(report: Any) -> list[VisualItem]:
    processors = report.discovered.get("processors", {})
    items: list[VisualItem] = []
    for name in sorted(processors):
        result = find_result(report, "processor", name)
        if result:
            items.append(VisualItem(name, result.status, result.detail, result.remediation))
    return items


def format_items(report: Any) -> list[VisualItem]:
    mapping = {
        "image_extra": "images: BMP/TIFF/GIF/WebP",
        "text_extra": "text: TXT/MD",
        "office_conversion": "office: DOC/PPT/XLS",
        "markdown_extra:markdown": "markdown package",
        "markdown_extra:weasyprint": "markdown PDF engine",
        "markdown_extra:pygments": "syntax highlighting",
    }
    items: list[VisualItem] = []
    for result in results_by_category(report, "formats"):
        if result.name in mapping:
            items.append(VisualItem(mapping[result.name], result.status, result.detail, result.remediation))
    pdf_renderer = find_result(report, "parser", "paddleocr_pdf_renderer")
    if pdf_renderer:
        items.append(VisualItem("paddleocr PDF renderer", pdf_renderer.status, pdf_renderer.detail, pdf_renderer.remediation))
    paddle = find_result(report, "parser", "paddlepaddle_runtime")
    if paddle:
        items.append(VisualItem("paddle runtime", paddle.status, paddle.detail, paddle.remediation))
    return items


def provider_items(report: Any) -> list[VisualItem]:
    names = [
        "LLM_BINDING",
        "LLM_API_KEY",
        "EMBEDDING_BINDING",
        "EMBEDDING_API_KEY",
        "ollama_cli",
    ]
    items: list[VisualItem] = []
    for name in names:
        result = find_result(report, "provider", name)
        if result:
            items.append(VisualItem(name, result.status, result.detail, result.remediation))
    for key in ("env:LLM_BINDING", "env:LLM_MODEL", "env:LLM_BINDING_HOST", "env:EMBEDDING_BINDING", "env:EMBEDDING_MODEL", "env:EMBEDDING_BINDING_HOST"):
        result = find_result(report, "config", key)
        if result and result.status == STATUS_FAIL:
            items.append(VisualItem(key.replace("env:", ""), STATUS_FAIL, result.detail, result.remediation))
    return items


def storage_items(report: Any) -> list[VisualItem]:
    items: list[VisualItem] = []
    for result in results_by_category(report, "storage"):
        if result.name == "declared_backends":
            continue
        items.append(VisualItem(result.name, result.status, result.detail, result.remediation))
    return items


def cli_items(report: Any) -> list[VisualItem]:
    items: list[VisualItem] = []
    for result in results_by_category(report, "cli"):
        if ":choices" in result.name:
            continue
        items.append(VisualItem(result.name, result.status, result.detail, result.remediation))
    return items


def coverage_items(report: Any) -> list[VisualItem]:
    items: list[VisualItem] = []
    for category in ("coverage", "exports", "api", "smoke"):
        for result in results_by_category(report, category):
            if category == "smoke" and result.name != "manifest":
                continue
            items.append(VisualItem(f"{category}:{result.name}", result.status, result.detail, result.remediation))
    return items


def print_rule(title: str, width: int, palette: Palette) -> None:
    left = f" {title} "
    fill = max(0, width - len(left))
    print(palette.dim(left + "-" * fill))


def print_header(report: Any, width: int, palette: Palette) -> None:
    counts = report.counts()
    title = "RAG-ANYTHING VISUAL CONSOLE TEST"
    print()
    print(palette.strong("=" * width))
    print(palette.strong(title.center(width)))
    print(palette.strong("=" * width))
    print(f"Project : {report.project_root}")
    print(f"RAG     : {report.rag_dir}")
    print(f"Config  : {report.config_path}")
    print(
        "Status  : "
        f"{palette.color('OK=' + str(counts.get(STATUS_OK, 0)), FG_OK)}  "
        f"{palette.color('WARN=' + str(counts.get(STATUS_WARN, 0)), FG_WARN)}  "
        f"{palette.color('FAIL=' + str(counts.get(STATUS_FAIL, 0)), FG_FAIL)}  "
        f"{palette.color('SKIP=' + str(counts.get(STATUS_SKIP, 0)), FG_SKIP)}"
    )
    discovered = report.discovered
    print(
        "Surface : "
        f"parsers={len(discovered.get('parsers', {}).get('names', []))}, "
        f"processors={len(discovered.get('processors', {}))}, "
        f"extras={len(discovered.get('pyproject', {}).get('optional_dependencies', {}))}, "
        f"env={len(discovered.get('env_surface', {}).get('all_keys', []))}, "
        f"exports={len(discovered.get('exports', {}).get('symbols', []))}"
    )
    print()


def print_section(title: str, items: list[VisualItem], width: int, palette: Palette, limit: int | None = None) -> None:
    print_rule(title, width, palette)
    if not items:
        print(f"  {status_mark(STATUS_SKIP, palette)} no items")
        print()
        return
    visible = items if limit is None else items[:limit]
    name_width = min(32, max(12, max(len(item.name) for item in visible)))
    for item in visible:
        mark = status_mark(item.status, palette)
        state = status_label(item.status, palette, 18)
        detail_width = width - name_width - 25
        detail = fit(item.detail, max(20, detail_width))
        print(f"  {mark} {item.name:<{name_width}} {state} {detail}")
        if item.status in {STATUS_FAIL, STATUS_WARN} and item.reason:
            print(f"       fix: {fit(item.reason, width - 12)}")
    if limit is not None and len(items) > limit:
        print(palette.dim(f"       ... {len(items) - limit} more"))
    print()


def print_decision_board(report: Any, width: int, palette: Palette) -> None:
    groups = [
        ("Core coverage", coverage_items(report)),
        ("Parsers", parser_items(report)),
        ("Modal processors", processor_items(report)),
        ("Formats and converters", format_items(report)),
        ("LLM and embeddings", provider_items(report)),
        ("Storage backends", storage_items(report)),
        ("CLI tools", cli_items(report)),
    ]
    print_rule("HIGH LEVEL READINESS", width, palette)
    for title, items in groups:
        status = worst_status([item.status for item in items])
        usable = {
            STATUS_OK: "ready",
            STATUS_WARN: "partial",
            STATUS_FAIL: "blocked",
            STATUS_SKIP: "not configured",
        }.get(status, "unknown")
        print(f"  {status_mark(status, palette)} {title:<24} {status_label(status, palette, 18)} {usable}")
    print()


def print_help_lines(report: Any, width: int, palette: Palette) -> None:
    blockers = [item for item in parser_items(report) + provider_items(report) + format_items(report) if item.status == STATUS_FAIL]
    warnings = [item for item in parser_items(report) + provider_items(report) + format_items(report) + cli_items(report) if item.status == STATUS_WARN]
    print_rule("WHAT TO FIX FIRST", width, palette)
    if not blockers and not warnings:
        print(f"  {status_mark(STATUS_OK, palette)} All checked runtime modules are usable.")
        print()
        return
    for item in blockers[:8]:
        reason = item.reason or item.detail
        print(f"  {status_mark(STATUS_FAIL, palette)} {item.name}: {fit(reason, width - len(item.name) - 8)}")
    for item in warnings[:6]:
        reason = item.reason or item.detail
        print(f"  {status_mark(STATUS_WARN, palette)} {item.name}: {fit(reason, width - len(item.name) - 8)}")
    print()


def print_visual_report(report: Any, palette: Palette) -> None:
    width = terminal_width()
    print_header(report, width, palette)
    print_decision_board(report, width, palette)
    print_section("PARSERS OFFERED BY RAG", parser_items(report), width, palette)
    print_section("MULTIMODAL MODULES", processor_items(report), width, palette)
    print_section("FORMATS / CONVERTERS", format_items(report), width, palette)
    print_section("LLM / EMBEDDING RUNTIME", provider_items(report), width, palette)
    print_section("STORAGE BACKENDS", storage_items(report), width, palette)
    print_section("CLI SURFACE", cli_items(report), width, palette)
    print_section("COVERAGE / API / EXPORTS", coverage_items(report), width, palette, limit=18)
    print_section("CONFIG GROUPS", env_group_items(report), width, palette, limit=30)
    print_help_lines(report, width, palette)
    print(palette.strong("=" * width))
    print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Visual console dashboard for RAG-Anything readiness.")
    parser.add_argument(
        "--config",
        default=str(project_root() / "configs" / "rag-tool-check.toml"),
        help="Path to checker TOML/JSON config.",
    )
    parser.add_argument("--python", default=None, help="Python executable used for import checks.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    parser.add_argument("--color", action="store_true", help="Enable ANSI colors. Disabled by default for Windows console compatibility.")
    parser.add_argument("--plain", action="store_true", help="Force plain output without ANSI colors.")
    parser.add_argument("--no-json-report", action="store_true", help="Do not write the JSON checker report.")
    parser.add_argument("--report-only", action="store_true", help="Always exit 0.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = project_root()
    config_path = resolve_path(root, args.config)
    config = load_config(config_path)
    checker = Checker(
        project_root=root,
        config_path=config_path,
        config=config,
        python_override=args.python,
        strict_override=args.strict,
    )
    report = checker.run()
    palette = Palette(enabled=bool(args.color and not args.plain and os.environ.get("NO_COLOR") is None))
    print_visual_report(report, palette)

    if not args.no_json_report:
        from rag_tool_check import write_report

        report_json = config.get("paths", {}).get("report_json")
        if report_json:
            write_report(resolve_path(root, str(report_json)), report)

    if args.report_only:
        return 0
    if report.has_failures() or (report.strict and report.has_warnings()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
