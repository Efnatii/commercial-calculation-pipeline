"""Russian labels and explanations for the visual RAG dashboard."""

PARSER_NOTES = {
    "mineru": "Основной парсер для PDF, сканов, изображений и сложных документов.",
    "docling": "Альтернативный парсер для Office/HTML/PDF через Python API Docling.",
    "paddleocr": "OCR-парсер для изображений и PDF, полезен для сканов.",
}

PROCESSOR_NOTES = {
    "image": "Анализ изображений, подписи, визуальное описание, сущности.",
    "table": "Разбор таблиц, статистика, тренды, извлечение табличных сущностей.",
    "equation": "Формулы, переменные, смысл математических выражений.",
    "generic": "Общий обработчик для нестандартных multimodal-блоков.",
}

FORMAT_NOTES = {
    "images: BMP/TIFF/GIF/WebP": "Расширенные форматы изображений через Pillow.",
    "text: TXT/MD": "Конвертация TXT/MD через ReportLab.",
    "office: DOC/PPT/XLS": "Office-документы требуют LibreOffice или soffice.",
    "markdown package": "Markdown-пакет для расширенной Markdown-обработки.",
    "markdown PDF engine": "WeasyPrint для PDF-рендера Markdown.",
    "syntax highlighting": "Pygments для подсветки кода в Markdown/PDF.",
    "paddleocr PDF renderer": "pypdfium2 рендерит страницы PDF для PaddleOCR.",
    "paddle runtime": "PaddlePaddle runtime нужен PaddleOCR.",
}

PROVIDER_NOTES = {
    "LLM_BINDING": "Тип LLM-провайдера: OpenAI, Ollama, LM Studio, vLLM и т.д.",
    "LLM_MODEL": "Название модели для генерации ответов и анализа.",
    "LLM_BINDING_HOST": "HTTP-адрес LLM-провайдера.",
    "EMBEDDING_BINDING": "Тип провайдера эмбеддингов.",
    "EMBEDDING_MODEL": "Модель эмбеддингов для индексации и поиска.",
    "EMBEDDING_BINDING_HOST": "HTTP-адрес сервиса эмбеддингов.",
    "ollama_cli": "Проверка локального Ollama CLI и списка моделей.",
}

STORAGE_NOTES = {
    "postgres": "PostgreSQL: хранилище KV, векторов и статусов документов.",
    "neo4j": "Neo4j: графовое хранилище.",
    "age": "Apache AGE: графовое хранилище поверх PostgreSQL.",
    "tidb": "TiDB: устаревшее upstream-хранилище.",
    "mongodb": "MongoDB: документное хранилище.",
    "milvus": "Milvus: векторное хранилище.",
    "qdrant": "Qdrant: векторное хранилище.",
    "redis": "Redis: кэш или лёгкое хранилище.",
}

CLI_NOTES = {
    "parser": "CLI одиночного парсинга документов.",
    "batch_parser": "CLI пакетного парсинга директорий и файлов.",
    "enhanced_markdown": "CLI конвертации Markdown в PDF.",
    "optional_tool:pandoc": "Pandoc нужен только для pandoc-режима Markdown-конвертера.",
}

COVERAGE_NOTES = {
    "coverage:parsers": "Все обнаруженные парсеры RAG-Anything отражены в конфиге проверки.",
    "coverage:processors": "Все мультимодальные модули отражены в конфиге проверки.",
    "coverage:optional_extras": "Все дополнительные зависимости из pyproject.toml учтены.",
    "coverage:env_keys": "Все env-переменные из env.example и кода разложены по группам конфига.",
    "coverage:cli:batch_parser": "Все аргументы batch parser CLI покрыты манифестом.",
    "coverage:cli:enhanced_markdown": "Все аргументы enhanced markdown CLI покрыты манифестом.",
    "coverage:cli:parser": "Все аргументы parser CLI покрыты манифестом.",
    "coverage:exports": "Все экспортируемые символы пакета сверены с манифестом.",
    "coverage:public_api": "Все публичные методы API сверены с манифестом.",
    "exports:callbacks": "Экспорты callback-модулей обнаружены и покрыты.",
    "exports:core": "Основные экспорты RAGAnything обнаружены и покрыты.",
    "exports:parser_registry": "Экспорты реестра парсеров обнаружены и покрыты.",
    "exports:prompt_manager": "Экспорты prompt manager обнаружены и покрыты.",
    "exports:resilience": "Экспорты resilience/устойчивости обнаружены и покрыты.",
    "api:batch_parser": "Публичные методы batch parser найдены в текущем submodule.",
    "api:batch_result": "Публичные методы результата batch parser найдены.",
    "api:markdown": "Публичные методы markdown-конвертера найдены.",
    "api:parser": "Публичные методы одиночного parser найдены.",
    "api:parser_classes": "Публичные классы и методы parser-слоя найдены.",
    "api:prompt_manager": "Публичные методы prompt manager найдены.",
    "api:raganything": "Публичные методы главного класса RAGAnything найдены.",
    "smoke:manifest": "Smoke-набор показывает, какие быстрые проверки включены, а какие выключены.",
}

SMOKE_NOTES = {
    "manifest": "Сводка включённых реальных runtime-проб.",
    "import_package_exports": "Проверяет, что пакет raganything импортируется и экспортирует заявленные символы.",
    "config_instantiation": "Создаёт RAGAnythingConfig и проверяет базовые поля без сети и моделей.",
    "rag_instance_config_info": "Создаёт объект RAGAnything и читает get_config_info без запуска парсинга.",
    "parser_registry_roundtrip": "Регистрирует временный custom parser, получает его через registry и удаляет обратно.",
    "processor_supports": "Вызывает карту поддерживаемых multimodal-процессоров image/table/equation/generic.",
    "callback_dispatch": "Создаёт CallbackManager, отправляет событие и проверяет event log.",
    "prompt_language_roundtrip": "Переключает prompt language manager в безопасном режиме и возвращает настройки.",
    "batch_dry_run": "Создаёт временный TXT-файл и запускает BatchParser dry-run без реального парсинга.",
    "cli_help:raganything.parser": "Реально запускает python -m raganything.parser --help.",
    "cli_help:raganything.batch_parser": "Реально запускает python -m raganything.batch_parser --help.",
    "cli_help:raganything.enhanced_markdown": "Реально запускает python -m raganything.enhanced_markdown --help.",
    "provider_endpoint_probe": "Сетевая проверка endpoint провайдера; по умолчанию выключена.",
    "storage_connection_probe": "Проверка подключения к внешним хранилищам; по умолчанию выключена.",
    "sample_ingest": "Полная пробная вставка документа в LightRAG; по умолчанию выключена.",
}

ENV_GROUP_NOTES = {
    "age": "Apache AGE: графовое хранилище поверх PostgreSQL.",
    "auth": "Аутентификация: login, JWT, API key и whitelist.",
    "batch": "Пакетная обработка файлов и директорий.",
    "context": "Настройки извлечения контекста вокруг найденных фрагментов.",
    "directories": "Пути входных файлов, выходных артефактов и рабочей директории.",
    "embedding": "Провайдер эмбеддингов, модель, размерность и Azure-настройки.",
    "llm": "LLM/VLM-провайдеры, модели, Azure/vLLM и кэширование.",
    "logging": "Логи: уровень, подробность, ротация и каталог логов.",
    "milvus": "Milvus: векторное хранилище.",
    "minimax_examples": "Переменные для MiniMax examples из upstream.",
    "mongodb": "MongoDB: документное/служебное хранилище.",
    "multimodal": "Переключатели обработки изображений, таблиц и формул.",
    "neo4j": "Neo4j: графовое хранилище.",
    "offline": "Офлайн-режим и локальный кэш моделей.",
    "ollama_examples": "Переменные для Ollama examples из upstream.",
    "parser": "Выбор parser-а и параметры разбора документов.",
    "postgres": "PostgreSQL: хранилище KV, векторов и статусов документов.",
    "public_assets": "Публичные URL для изображений и таблиц, созданных при парсинге.",
    "qdrant": "Qdrant: векторное хранилище.",
    "query": "RAG-запросы: graph, rerank, chunking и лимиты токенов.",
    "redis": "Redis: кэш или лёгкое хранилище.",
    "server": "LightRAG API/WebUI server.",
    "ssl": "SSL-сертификаты для серверного режима.",
    "storage_selection": "Выбор классов хранилищ LightRAG.",
    "tidb": "TiDB: устаревшая upstream-настройка storage.",
}

SECTION_NOTES = {
    "ПАРСЕРЫ, КОТОРЫЕ ДАЁТ RAG": "Парсеры превращают PDF, сканы, Office-файлы и изображения в структурированный список контента.",
    "МУЛЬТИМОДАЛЬНЫЕ МОДУЛИ": "Эти модули анализируют уже извлечённые изображения, таблицы, формулы и нестандартные блоки.",
    "ФОРМАТЫ И КОНВЕРТЕРЫ": "Здесь видно, какие типы файлов эта машина реально сможет обработать без ручной подготовки.",
    "LLM И ЭМБЕДДИНГИ": "Без этих настроек RAG может парсить файлы, но полноценный поиск и ответы не готовы.",
    "ХРАНИЛИЩА": "Хранилища включаются только если выбраны через LIGHTRAG_* env-переменные.",
    "CLI-ПОВЕРХНОСТЬ": "Командные интерфейсы RAG-Anything, которые можно запускать из консоли.",
    "ПОКРЫТИЕ, API И ЭКСПОРТЫ": "Проверка, что внешняя обвязка покрывает весь текущий набор возможностей RAG-Anything.",
    "ГРУППЫ КОНФИГА": "Группы настроек из env.example и кода RAG-Anything.",
}

GROUP_NOTES = {
    "Покрытие обвязки": "Проверяет, не появилась ли в RAG-Anything новая возможность, которой ещё нет в нашем конфиге.",
    "Парсеры": "Это входной слой: без него RAG не сможет нормально разобрать PDF, сканы и сложные документы.",
    "Мультимодальные модули": "Это анализ уже извлечённых блоков: картинки, таблицы, формулы и прочий контент.",
    "Форматы и конвертеры": "Показывает, какие типы файлов будут обработаны сразу, а для каких нужны внешние пакеты.",
    "LLM и эмбеддинги": "Это слой поиска и ответов: LLM генерирует ответ, эмбеддинги строят индекс и поиск.",
    "Хранилища": "Дополнительные хранилища LightRAG. Они не считаются ошибкой, пока не выбраны в env.",
    "CLI инструменты": "Команды RAG-Anything, которые можно запускать напрямую из консоли.",
    "Реальные smoke-пробы": "Проверяет не только описание возможностей, а быстрый фактический запуск RAG-Anything без сети и тяжёлого парсинга.",
}
