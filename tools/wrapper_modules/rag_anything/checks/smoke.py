from __future__ import annotations

import socket
import textwrap
import urllib.parse
from typing import Any

from wrapper_modules.rag_anything.core.config import as_list, parse_bool
from wrapper_modules.rag_anything.core.models import STATUS_FAIL, STATUS_OK, STATUS_SKIP, STATUS_WARN
from wrapper_modules.rag_anything.core.process import python_code_check, python_env, run_command

SMOKE_TEST_ORDER = (
    "import_package_exports",
    "config_instantiation",
    "rag_instance_config_info",
    "parser_registry_roundtrip",
    "processor_supports",
    "callback_dispatch",
    "prompt_language_roundtrip",
    "batch_dry_run",
    "cli_help",
    "provider_endpoint_probe",
    "storage_connection_probe",
    "sample_ingest",
)

PACKAGE_IMPORT_DEPENDENT_TESTS = {
    "config_instantiation",
    "rag_instance_config_info",
    "parser_registry_roundtrip",
    "processor_supports",
    "callback_dispatch",
    "prompt_language_roundtrip",
    "batch_dry_run",
}

DEFAULT_REQUIRED_TESTS = {
    "import_package_exports",
    "config_instantiation",
    "rag_instance_config_info",
    "parser_registry_roundtrip",
    "processor_supports",
    "callback_dispatch",
    "prompt_language_roundtrip",
    "batch_dry_run",
    "cli_help",
}

DEFAULT_CLI_HELP_MODULES = (
    "raganything.parser",
    "raganything.batch_parser",
    "raganything.enhanced_markdown",
)


def _bool_setting(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return parse_bool(value, default)
    return bool(value) if value is not None else default


def _test_enabled(smoke: dict[str, Any], name: str) -> bool:
    raw = smoke.get(name, False)
    if isinstance(raw, dict):
        return _bool_setting(raw.get("enabled"), False)
    return _bool_setting(raw, False)


def _test_required(smoke: dict[str, Any], name: str) -> bool:
    raw = smoke.get(name, False)
    if isinstance(raw, dict) and "required" in raw:
        return _bool_setting(raw.get("required"), False)
    required = {str(item) for item in as_list(smoke.get("required", []))}
    optional = {str(item) for item in as_list(smoke.get("optional", []))}
    if name in required:
        return True
    if name in optional:
        return False
    return name in DEFAULT_REQUIRED_TESTS


def _status(ok: bool, required: bool) -> str:
    if ok:
        return STATUS_OK
    return STATUS_FAIL if required else STATUS_WARN


def _add(
    checker: Any,
    name: str,
    ok: bool,
    detail: str,
    required: bool,
    remediation: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    checker.add(
        "smoke",
        name,
        _status(ok, required),
        detail,
        required=required,
        remediation=remediation,
        metadata={"runtime_probe": True, **(metadata or {})},
    )


def _skip(checker: Any, name: str, detail: str, metadata: dict[str, Any] | None = None) -> None:
    checker.add(
        "smoke",
        name,
        STATUS_SKIP,
        detail,
        metadata={"runtime_probe": True, **(metadata or {})},
    )


def _run_python_smoke(checker: Any, code: str) -> tuple[bool, str]:
    return python_code_check(
        checker.python,
        textwrap.dedent(code).strip(),
        checker.timeout,
        extra_pythonpath=checker.rag_dir,
        cwd=checker.rag_dir,
    )


def _import_package_exports(checker: Any) -> tuple[bool, str]:
    symbols = sorted(checker.configured_export_symbols())
    code = f"""
        import importlib
        module = importlib.import_module("raganything")
        symbols = {symbols!r}
        missing = [name for name in symbols if not hasattr(module, name)]
        assert not missing, missing
        print(f"raganything imported; exports checked={{len(symbols)}}")
    """
    return _run_python_smoke(checker, code)


def _config_instantiation(checker: Any) -> tuple[bool, str]:
    code = """
        import tempfile
        from pathlib import Path
        from raganything import RAGAnythingConfig

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = RAGAnythingConfig(
                working_dir=str(root / "work"),
                parser_output_dir=str(root / "out"),
                parser="mineru",
                parse_method="auto",
                enable_image_processing=False,
                enable_table_processing=False,
                enable_equation_processing=False,
            )
            assert cfg.parser == "mineru"
            assert cfg.parse_method == "auto"
            assert cfg.working_dir.endswith("work")
            assert ".pdf" in cfg.supported_file_extensions
            print(f"config instantiated; extensions={len(cfg.supported_file_extensions)}")
    """
    return _run_python_smoke(checker, code)


def _rag_instance_config_info(checker: Any) -> tuple[bool, str]:
    code = """
        import tempfile
        from pathlib import Path
        from raganything import RAGAnything, RAGAnythingConfig

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = RAGAnythingConfig(
                working_dir=str(root / "work"),
                parser_output_dir=str(root / "out"),
                parser="mineru",
                parse_method="auto",
                enable_image_processing=False,
                enable_table_processing=False,
                enable_equation_processing=False,
            )
            rag = RAGAnything(config=cfg)
            info = rag.get_config_info()
            assert info["parsing"]["parser"] == "mineru"
            assert info["multimodal_processing"]["enable_image_processing"] is False
            assert Path(cfg.working_dir).exists()
            rag.close()
            print("RAGAnything instance created and config info returned")
    """
    return _run_python_smoke(checker, code)


def _parser_registry_roundtrip(checker: Any) -> tuple[bool, str]:
    code = """
        from raganything.parser import Parser, get_parser, get_supported_parsers, list_parsers, register_parser, unregister_parser

        class SmokeParser(Parser):
            def check_installation(self):
                return True

            def parse_document(self, file_path, output_dir="./output", method="auto", **kwargs):
                return [{"type": "text", "text": "smoke"}]

        register_parser("codex_smoke", SmokeParser)
        try:
            assert "codex_smoke" in list_parsers()
            assert "codex_smoke" in get_supported_parsers()
            parser = get_parser("codex_smoke")
            assert parser.check_installation() is True
            assert parser.parse_document("sample.txt")[0]["text"] == "smoke"
            print("custom parser registry roundtrip works")
        finally:
            unregister_parser("codex_smoke")
    """
    return _run_python_smoke(checker, code)


def _processor_supports(checker: Any) -> tuple[bool, str]:
    code = """
        from raganything.utils import get_processor_supports

        expected = ("image", "table", "equation", "generic")
        supports = {name: get_processor_supports(name) for name in expected}
        assert all(supports.values()), supports
        assert "Image content analysis" in supports["image"]
        assert "Table structure analysis" in supports["table"]
        assert "Mathematical formula parsing" in supports["equation"]
        print("processor support map works for image/table/equation/generic")
    """
    return _run_python_smoke(checker, code)


def _callback_dispatch(checker: Any) -> tuple[bool, str]:
    code = """
        from raganything.callbacks import CallbackManager, ProcessingCallback

        class Capture(ProcessingCallback):
            def __init__(self):
                self.events = []

            def on_parse_start(self, file_path, parser="", **kwargs):
                self.events.append((file_path, parser))

        manager = CallbackManager()
        callback = Capture()
        manager.register(callback)
        manager.enable_event_log(True)
        manager.dispatch("on_parse_start", file_path="sample.txt", parser="mineru")
        assert callback.events == [("sample.txt", "mineru")]
        assert len(manager.event_log) == 1
        manager.unregister(callback)
        print("callback manager dispatch and event log work")
    """
    return _run_python_smoke(checker, code)


def _prompt_language_roundtrip(checker: Any) -> tuple[bool, str]:
    code = """
        from raganything.prompt_manager import get_available_languages, get_prompt_language, reset_prompts, set_prompt_language

        set_prompt_language("en")
        assert get_prompt_language() == "en"
        assert "zh" in get_available_languages()
        reset_prompts()
        assert get_prompt_language() == "en"
        print("prompt language manager roundtrip works")
    """
    return _run_python_smoke(checker, code)


def _batch_dry_run(checker: Any) -> tuple[bool, str]:
    code = """
        import tempfile
        from pathlib import Path
        from raganything.batch_parser import BatchParser

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            docs.mkdir()
            sample = docs / "sample.txt"
            sample.write_text("smoke document", encoding="utf-8")
            parser = BatchParser(
                parser_type="mineru",
                show_progress=False,
                skip_installation_check=True,
            )
            result = parser.process_batch(
                file_paths=[str(docs)],
                output_dir=str(root / "out"),
                recursive=True,
                dry_run=True,
            )
            assert result.dry_run is True
            assert result.total_files == 1
            assert result.successful_files == [str(sample)]
            assert result.failed_files == []
            print("batch parser dry-run scanned one supported TXT file")
    """
    return _run_python_smoke(checker, code)


def _cli_help(checker: Any, smoke: dict[str, Any]) -> list[tuple[str, bool, str]]:
    modules = tuple(str(item) for item in as_list(smoke.get("cli_help_modules", list(DEFAULT_CLI_HELP_MODULES))))
    results: list[tuple[str, bool, str]] = []
    env = python_env(checker.rag_dir)
    for module in modules:
        ok, output, _ = run_command(
            [checker.python, "-m", module, "--help"],
            checker.timeout,
            cwd=checker.rag_dir,
            env=env,
        )
        detail = f"{module} --help exits 0" if ok else output
        results.append((module, ok, detail))
    return results


def _network_probe_enabled(checker: Any) -> bool:
    return _bool_setting(checker.execution.get("network_checks"), False)


def _storage_probe_enabled(checker: Any) -> bool:
    return _bool_setting(checker.execution.get("storage_connection_checks"), False)


def _sample_ingest_enabled(checker: Any) -> bool:
    return _bool_setting(checker.execution.get("sample_ingest_checks"), False)


def _tcp_probe(target: str, timeout_seconds: int) -> tuple[bool, str]:
    parsed = urllib.parse.urlparse(target)
    if parsed.scheme and parsed.hostname:
        host = parsed.hostname
        if parsed.port:
            port = parsed.port
        elif parsed.scheme == "https":
            port = 443
        elif parsed.scheme == "http":
            port = 80
        elif parsed.scheme in {"redis", "rediss"}:
            port = 6379
        elif parsed.scheme in {"bolt", "neo4j"}:
            port = 7687
        elif parsed.scheme in {"mongodb", "mongodb+srv"}:
            port = 27017
        elif parsed.scheme in {"postgres", "postgresql"}:
            port = 5432
        else:
            return False, f"Cannot infer TCP port from URL scheme: {parsed.scheme}"
    elif ":" in target:
        host, raw_port = target.rsplit(":", 1)
        try:
            port = int(raw_port)
        except ValueError:
            return False, f"Invalid host:port target: {target}"
    else:
        return False, f"Expected URL or host:port, got: {target}"
    try:
        with socket.create_connection((host, int(port)), timeout=min(timeout_seconds, 5)):
            return True, f"TCP connection opened to {host}:{port}"
    except OSError as exc:
        return False, f"TCP connection failed to {host}:{port}: {exc}"


def _provider_targets(env: dict[str, str]) -> dict[str, str]:
    targets = {}
    for key in ("LLM_BINDING_HOST", "EMBEDDING_BINDING_HOST"):
        value = str(env.get(key, "")).strip()
        if value:
            targets[key] = value
    return targets


def _storage_targets(env: dict[str, str]) -> dict[str, str]:
    targets: dict[str, str] = {}
    direct_url_keys = {
        "NEO4J_URI": "neo4j",
        "REDIS_URI": "redis",
        "QDRANT_URL": "qdrant",
        "MONGO_URI": "mongodb",
        "MILVUS_URI": "milvus",
    }
    for key, label in direct_url_keys.items():
        value = str(env.get(key, "")).strip()
        if value:
            targets[label] = value
    host_port_keys = {
        "postgres": ("POSTGRES_HOST", "POSTGRES_PORT", "5432"),
        "age": ("AGE_POSTGRES_HOST", "AGE_POSTGRES_PORT", "5432"),
        "tidb": ("TIDB_HOST", "TIDB_PORT", "4000"),
        "milvus": ("MILVUS_HOST", "MILVUS_PORT", "19530"),
    }
    for label, (host_key, port_key, default_port) in host_port_keys.items():
        host = str(env.get(host_key, "")).strip()
        if host and label not in targets:
            port = str(env.get(port_key, default_port)).strip() or default_port
            targets[label] = f"{host}:{port}"
    return targets


PYTHON_SMOKE_TESTS = {
    "config_instantiation": _config_instantiation,
    "rag_instance_config_info": _rag_instance_config_info,
    "parser_registry_roundtrip": _parser_registry_roundtrip,
    "processor_supports": _processor_supports,
    "callback_dispatch": _callback_dispatch,
    "prompt_language_roundtrip": _prompt_language_roundtrip,
    "batch_dry_run": _batch_dry_run,
}


def check_smoke_manifest(checker: Any) -> None:
    smoke = checker.config.get("smoke_tests", {})
    if not smoke:
        return
    if not isinstance(smoke, dict):
        checker.add("smoke", "manifest", STATUS_WARN, "smoke_tests config must be a table")
        return

    smoke_enabled = _bool_setting(checker.execution.get("smoke_tests"), True)
    enabled = [name for name in SMOKE_TEST_ORDER if _test_enabled(smoke, name)]
    disabled = [name for name in SMOKE_TEST_ORDER if name not in enabled]
    checker.add(
        "smoke",
        "manifest",
        STATUS_OK if smoke_enabled else STATUS_SKIP,
        (
            f"real runtime probes enabled={', '.join(enabled) if enabled else 'none'}; "
            f"disabled={len(disabled)}"
        ),
        metadata={"runtime_probe": True, "enabled": enabled, "disabled": disabled},
    )
    if not smoke_enabled:
        return

    package_import_failed = False
    package_import_error = ""

    if _test_enabled(smoke, "import_package_exports"):
        required = _test_required(smoke, "import_package_exports")
        ok, output = _import_package_exports(checker)
        if not ok:
            package_import_failed = True
            package_import_error = output
        _add(
            checker,
            "import_package_exports",
            ok,
            output if ok else output,
            required,
            remediation="Установить runtime-зависимости RAG-Anything, минимум python-dotenv, затем повторить smoke-проверки.",
        )

    for name, function in PYTHON_SMOKE_TESTS.items():
        if not _test_enabled(smoke, name):
            continue
        if package_import_failed and name in PACKAGE_IMPORT_DEPENDENT_TESTS:
            _skip(
                checker,
                name,
                f"Заблокировано: сначала не импортируется raganything: {package_import_error}",
            )
            continue
        required = _test_required(smoke, name)
        ok, output = function(checker)
        _add(
            checker,
            name,
            ok,
            output if ok else output,
            required,
            remediation="Исправить runtime-ошибку из строки проверки и повторить smoke-проверки.",
        )

    if _test_enabled(smoke, "cli_help"):
        required = _test_required(smoke, "cli_help")
        modules = tuple(str(item) for item in as_list(smoke.get("cli_help_modules", list(DEFAULT_CLI_HELP_MODULES))))
        if package_import_failed:
            for module in modules:
                _skip(
                    checker,
                    f"cli_help:{module}",
                    f"Заблокировано: сначала не импортируется raganything: {package_import_error}",
                    metadata={"module": module},
                )
        else:
            for module, ok, detail in _cli_help(checker, smoke):
                result_name = f"cli_help:{module}"
                _add(
                    checker,
                    result_name,
                    ok,
                    detail,
                    required,
                    remediation="Исправить импорт пакета или CLI-зависимости перед использованием этой команды.",
                    metadata={"module": module},
                )

    if _test_enabled(smoke, "provider_endpoint_probe") and not _network_probe_enabled(checker):
        _skip(
            checker,
            "provider_endpoint_probe",
            "Disabled by execution.network_checks=false; no network endpoint was contacted.",
        )
    elif _test_enabled(smoke, "provider_endpoint_probe"):
        env = getattr(checker, "_checked_env", {})
        targets = _provider_targets(env)
        if not targets:
            _skip(checker, "provider_endpoint_probe", "No provider endpoint env values are set.")
        for key, target in targets.items():
            required = _test_required(smoke, "provider_endpoint_probe")
            ok, detail = _tcp_probe(target, checker.timeout)
            _add(
                checker,
                f"provider_endpoint_probe:{key}",
                ok,
                detail,
                required,
                remediation=f"Проверить {key}, статус локального сервиса, firewall и проброс порта.",
            )

    if _test_enabled(smoke, "storage_connection_probe") and not _storage_probe_enabled(checker):
        _skip(
            checker,
            "storage_connection_probe",
            "Disabled by execution.storage_connection_checks=false; no external storage was contacted.",
        )
    elif _test_enabled(smoke, "storage_connection_probe"):
        env = getattr(checker, "_checked_env", {})
        targets = _storage_targets(env)
        if not targets:
            _skip(checker, "storage_connection_probe", "No storage endpoint env values are set.")
        for label, target in targets.items():
            required = _test_required(smoke, "storage_connection_probe")
            ok, detail = _tcp_probe(target, checker.timeout)
            _add(
                checker,
                f"storage_connection_probe:{label}",
                ok,
                detail,
                required,
                remediation=f"Проверить сервис {label}, credentials, host, firewall и проброс порта.",
            )

    if _test_enabled(smoke, "sample_ingest") and not _sample_ingest_enabled(checker):
        _skip(
            checker,
            "sample_ingest",
            "Disabled by execution.sample_ingest_checks=false; no document was inserted into LightRAG.",
        )
    elif _test_enabled(smoke, "sample_ingest"):
        required = _test_required(smoke, "sample_ingest")
        _add(
            checker,
            "sample_ingest",
            False,
            "Полный ingest smoke не выполняется безопасным чекером; для него нужны реальные LLM и embedding functions.",
            required,
            remediation="Запускать через отдельный integration-test профиль с реальными LLM и embedding functions.",
        )
