from __future__ import annotations

from typing import Any

from wrapper_modules.rag_anything.console.catalog import (
    CLI_NOTES,
    COVERAGE_NOTES,
    ENV_GROUP_NOTES,
    FORMAT_NOTES,
    PARSER_NOTES,
    PROCESSOR_NOTES,
    PROVIDER_NOTES,
    SMOKE_NOTES,
    STORAGE_NOTES,
)
from wrapper_modules.rag_anything.console.text import worst_status
from wrapper_modules.rag_anything.console.types import VisualItem
from wrapper_modules.rag_anything.core.models import STATUS_FAIL, STATUS_OK, STATUS_SKIP, STATUS_WARN

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
        items.append(VisualItem(name=name, status=result.status, detail=result.detail, note=ENV_GROUP_NOTES.get(name, "")))
    return items

def parser_items(report: Any) -> list[VisualItem]:
    discovered = report.discovered.get("parsers", {}).get("names", [])
    items: list[VisualItem] = []
    for name in discovered:
        result = find_result(report, "parser", str(name))
        if result is None:
            items.append(
                VisualItem(
                    str(name),
                    STATUS_SKIP,
                    "предлагается RAG-Anything, но не проверен",
                    note=PARSER_NOTES.get(str(name), ""),
                )
            )
        else:
            items.append(
                VisualItem(
                    str(name),
                    result.status,
                    result.detail,
                    result.remediation,
                    PARSER_NOTES.get(str(name), ""),
                )
            )
    return items

def processor_items(report: Any) -> list[VisualItem]:
    processors = report.discovered.get("processors", {})
    items: list[VisualItem] = []
    for name in sorted(processors):
        result = find_result(report, "processor", name)
        if result:
            items.append(VisualItem(name, result.status, result.detail, result.remediation, PROCESSOR_NOTES.get(name, "")))
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
            label = mapping[result.name]
            items.append(VisualItem(label, result.status, result.detail, result.remediation, FORMAT_NOTES.get(label, "")))
    pdf_renderer = find_result(report, "parser", "paddleocr_pdf_renderer")
    if pdf_renderer:
        label = "paddleocr PDF renderer"
        items.append(VisualItem(label, pdf_renderer.status, pdf_renderer.detail, pdf_renderer.remediation, FORMAT_NOTES.get(label, "")))
    paddle = find_result(report, "parser", "paddlepaddle_runtime")
    if paddle:
        label = "paddle runtime"
        items.append(VisualItem(label, paddle.status, paddle.detail, paddle.remediation, FORMAT_NOTES.get(label, "")))
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
            items.append(VisualItem(name, result.status, result.detail, result.remediation, PROVIDER_NOTES.get(name, "")))
    for key in ("env:LLM_BINDING", "env:LLM_MODEL", "env:LLM_BINDING_HOST", "env:EMBEDDING_BINDING", "env:EMBEDDING_MODEL", "env:EMBEDDING_BINDING_HOST"):
        result = find_result(report, "config", key)
        if result and result.status == STATUS_FAIL:
            label = key.replace("env:", "")
            items.append(VisualItem(label, STATUS_FAIL, result.detail, result.remediation, PROVIDER_NOTES.get(label, "")))
    return items

def storage_items(report: Any) -> list[VisualItem]:
    items: list[VisualItem] = []
    for result in results_by_category(report, "storage"):
        if result.name == "declared_backends":
            continue
        items.append(VisualItem(result.name, result.status, result.detail, result.remediation, STORAGE_NOTES.get(result.name, "")))
    return items

def cli_items(report: Any) -> list[VisualItem]:
    items: list[VisualItem] = []
    for result in results_by_category(report, "cli"):
        if ":choices" in result.name:
            continue
        items.append(VisualItem(result.name, result.status, result.detail, result.remediation, CLI_NOTES.get(result.name, "")))
    return items

def coverage_items(report: Any) -> list[VisualItem]:
    items: list[VisualItem] = []
    for category in ("coverage", "exports", "api"):
        for result in results_by_category(report, category):
            key = f"{category}:{result.name}"
            items.append(VisualItem(key, result.status, result.detail, result.remediation, COVERAGE_NOTES.get(key, "")))
    return items

def smoke_items(report: Any) -> list[VisualItem]:
    items: list[VisualItem] = []
    for result in results_by_category(report, "smoke"):
        items.append(
            VisualItem(
                result.name,
                result.status,
                result.detail,
                result.remediation,
                SMOKE_NOTES.get(result.name, ""),
            )
        )
    return items

def summary_status(report: Any, pairs: list[tuple[str, str]]) -> str:
    statuses: list[str] = []
    for category, name in pairs:
        result = find_result(report, category, name)
        if result:
            statuses.append(result.status)
    return worst_status(statuses)

def coverage_summary_items(report: Any) -> list[VisualItem]:
    return [
        VisualItem("парсеры", summary_status(report, [("coverage", "parsers")]), "coverage"),
        VisualItem("мультимодальные модули", summary_status(report, [("coverage", "processors")]), "coverage"),
        VisualItem("доп. зависимости", summary_status(report, [("coverage", "optional_extras")]), "coverage"),
        VisualItem("env-переменные", summary_status(report, [("coverage", "env_keys")]), "coverage"),
        VisualItem(
            "CLI-аргументы",
            summary_status(
                report,
                [
                    ("coverage", "cli:batch_parser"),
                    ("coverage", "cli:enhanced_markdown"),
                    ("coverage", "cli:parser"),
                ],
            ),
            "coverage",
        ),
        VisualItem("публичный API", summary_status(report, [("coverage", "public_api")]), "coverage"),
        VisualItem("экспорты пакета", summary_status(report, [("coverage", "exports")]), "coverage"),
    ]

def env_group_summary_items(report: Any) -> list[VisualItem]:
    wanted = [
        ("parser", "парсер"),
        ("multimodal", "мультимодальность"),
        ("llm", "LLM"),
        ("embedding", "эмбеддинги"),
        ("query", "поиск/query"),
        ("context", "контекст"),
        ("storage_selection", "выбор хранилищ"),
        ("postgres", "PostgreSQL"),
        ("neo4j", "Neo4j"),
        ("qdrant", "Qdrant"),
        ("redis", "Redis"),
        ("server", "сервер"),
        ("auth", "авторизация"),
        ("logging", "логи"),
    ]
    by_name = {item.name: item for item in env_group_items(report)}
    result: list[VisualItem] = []
    for source_name, label in wanted:
        source = by_name.get(source_name)
        if source:
            result.append(VisualItem(label, source.status, source.detail, source.reason, source.note))
    return result

def group_rows(report: Any) -> list[tuple[str, list[VisualItem]]]:
    return [
        ("ПАРСЕРЫ", parser_items(report)),
        ("МУЛЬТИМОДАЛЬНОСТЬ", processor_items(report)),
        ("ФОРМАТЫ", format_items(report)),
        ("LLM + ЭМБЕДДИНГИ", provider_items(report)),
        ("ХРАНИЛИЩА", storage_items(report)),
        ("CLI", cli_items(report)),
    ]

def status_counts(items: list[VisualItem]) -> tuple[int, int, int, int]:
    ok = sum(1 for item in items if item.status == STATUS_OK)
    warn = sum(1 for item in items if item.status == STATUS_WARN)
    fail = sum(1 for item in items if item.status == STATUS_FAIL)
    skip = sum(1 for item in items if item.status == STATUS_SKIP)
    return ok, warn, fail, skip

__all__ = [
    "result_map", "results_by_category", "find_result", "env_group_items", "parser_items", "processor_items",
    "format_items", "provider_items", "storage_items", "cli_items", "coverage_items", "smoke_items", "summary_status",
    "coverage_summary_items", "env_group_summary_items", "group_rows", "status_counts",
]
