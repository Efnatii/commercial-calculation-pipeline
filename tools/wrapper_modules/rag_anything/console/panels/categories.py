from __future__ import annotations

from typing import Any

from wrapper_modules.rag_anything.console.items import (
    cli_items,
    coverage_summary_items,
    env_group_summary_items,
    format_items,
    parser_items,
    processor_items,
    provider_items,
    smoke_items,
    storage_items,
)
from wrapper_modules.rag_anything.console.palette import Palette
from wrapper_modules.rag_anything.console.panels.common import print_category_card
from wrapper_modules.rag_anything.console.text import print_rule, print_wrapped

def print_category_breakdown(report: Any, width: int, palette: Palette) -> None:
    print_rule("РАСШИФРОВКА КАТЕГОРИЙ", width, palette)
    print_wrapped(
        "Этот блок показывает, что именно спрятано за крупными группами на карте модулей: модули, env-переменные, "
        "внешние программы и проверки покрытия.",
        width,
        indent="  ",
        palette=palette,
        dim=True,
    )

    print_category_card(
        "ПАРСЕРЫ",
        parser_items(report),
        "Входной слой. Он превращает исходные файлы в структуру, которую дальше могут читать мультимодальные модули и RAG.",
        "PARSER, PARSE_METHOD, MINERU_PARSE_METHOD, INPUT_DIR, OUTPUT_DIR, WORKING_DIR",
        width,
        palette,
        "mineru - основной тяжёлый парсер PDF/сканов; docling - альтернативный парсер Office/HTML/PDF; paddleocr - OCR для сканов и изображений.",
        settings_label="переменные",
    )

    print_category_card(
        "МУЛЬТИМОДАЛЬНОСТЬ",
        processor_items(report),
        "Анализирует уже извлечённые части документа: картинки, таблицы, формулы и нестандартные блоки.",
        "ENABLE_IMAGE_PROCESSING, ENABLE_TABLE_PROCESSING, ENABLE_EQUATION_PROCESSING",
        width,
        palette,
        "image описывает изображения, table разбирает таблицы, equation разбирает формулы, generic обрабатывает прочие блоки.",
        settings_label="переменные",
    )

    print_category_card(
        "ФОРМАТЫ И КОНВЕРТЕРЫ",
        format_items(report),
        "Показывает, какие типы файлов эта машина реально сможет принять без ручной конвертации.",
        "Pillow, ReportLab, LibreOffice/soffice, markdown, WeasyPrint, Pygments, pypdfium2, PaddlePaddle",
        width,
        palette,
        "Если формат ограничен, RAG может работать с частью файлов, но конкретный тип документа будет требовать установки пакета.",
        settings_label="зависимости",
    )

    print_category_card(
        "LLM И ЭМБЕДДИНГИ",
        provider_items(report),
        "Слой поиска и ответов. LLM формирует ответы, а эмбеддинги строят индекс для семантического поиска.",
        "LLM_BINDING, LLM_MODEL, LLM_BINDING_HOST, LLM_BINDING_API_KEY, EMBEDDING_BINDING, EMBEDDING_MODEL, EMBEDDING_DIM, EMBEDDING_BINDING_HOST, EMBEDDING_BINDING_API_KEY",
        width,
        palette,
        "Поддерживаемые типы подключения: openai, ollama, lollms, azure_openai, lmstudio, vllm. Для OpenAI/Azure обычно нужен API key.",
        settings_label="переменные",
    )

    print_category_card(
        "ХРАНИЛИЩА",
        storage_items(report),
        "Дополнительные хранилища LightRAG. Они нужны, когда хочешь хранить KV, векторы, граф или статус документов вне обычного локального режима.",
        "LIGHTRAG_KV_STORAGE, LIGHTRAG_VECTOR_STORAGE, LIGHTRAG_DOC_STATUS_STORAGE, LIGHTRAG_GRAPH_STORAGE",
        width,
        palette,
        "Ключи конкретных хранилищ: POSTGRES_*, NEO4J_*, AGE_*, TIDB_*, MONGO_*, MILVUS_*, QDRANT_URL, REDIS_URI.",
        settings_label="выбор",
    )

    print_category_card(
        "CLI",
        cli_items(report),
        "Команды RAG-Anything, которые можно запускать напрямую без подключения MCP/plugin к Codex.",
        "raganything.parser, raganything.batch_parser, raganything.enhanced_markdown, pandoc необязательный",
        width,
        palette,
        "parser - один документ; batch_parser - пачка файлов/папок; enhanced_markdown - Markdown в PDF; pandoc нужен только для pandoc-режима.",
        settings_label="команды",
    )

    coverage = coverage_summary_items(report)
    print_category_card(
        "ПОКРЫТИЕ ОБВЯЗКИ",
        coverage,
        "Контроль, что внешний конфиг не отстал от текущего кода RAG-Anything.",
        "парсеры, мультимодальные модули, дополнительные зависимости, env-переменные, CLI-аргументы, публичный API, экспорты пакета",
        width,
        palette,
        "Если в исходном RAG-Anything появится новая возможность, проверка покрытия должна подсветить её, пока конфиг не обновлён явно.",
        settings_label="покрывает",
    )

    smoke = smoke_items(report)
    print_category_card(
        "РЕАЛЬНЫЕ SMOKE-ПРОВЕРКИ",
        smoke,
        "Этот блок уже не просто сверяет наличие флагов. Он запускает быстрые безопасные куски RAG-Anything: импорт пакета, конфиг, объект RAGAnything, registry, callbacks, processor map, dry-run batch и CLI --help.",
        "без сети, без моделей, без storage-подключений и без тяжёлого парсинга",
        width,
        palette,
        "Если здесь ошибка, значит проблема воспроизводится в реальном Python-запуске. Если стоит НЕ ВКЛЮЧЕНО, проба намеренно отключена, потому что требует сети, внешнего хранилища или полного ingest.",
        settings_label="запускает",
    )

    env_groups = env_group_summary_items(report)
    print_category_card(
        "КОНФИГ / ENV-ГРУППЫ",
        env_groups,
        "Группы переменных из env.example и кода RAG-Anything. В обычном экране показана только сводка, полный список доступен через -Details.",
        "parser, multimodal, llm, embedding, query, context, storage_selection, postgres, neo4j, qdrant, redis, server, auth, logging",
        width,
        palette,
        f"Важных групп здесь: {len(env_groups)}. Полный список всех ключей и их заполненность смотри в -Details.",
        settings_label="группы",
    )

__all__ = ["print_category_breakdown"]
