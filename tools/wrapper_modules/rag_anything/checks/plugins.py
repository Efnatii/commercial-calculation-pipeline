from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from wrapper_modules.rag_anything.checks.api import check_exports_and_api
from wrapper_modules.rag_anything.checks.cli import check_cli_manifest
from wrapper_modules.rag_anything.checks.coverage import check_coverage_manifest
from wrapper_modules.rag_anything.checks.discovery import check_discovery
from wrapper_modules.rag_anything.checks.environment import check_env_files, check_env_values
from wrapper_modules.rag_anything.checks.formats import check_format_features
from wrapper_modules.rag_anything.checks.parsers import check_parsers
from wrapper_modules.rag_anything.checks.processors import check_processors
from wrapper_modules.rag_anything.checks.project import check_project
from wrapper_modules.rag_anything.checks.providers import check_provider_config, check_provider_tools
from wrapper_modules.rag_anything.checks.smoke import check_smoke_manifest
from wrapper_modules.rag_anything.checks.storage import check_storage_backends
from wrapper_modules.rag_anything.core.models import CheckResult


CheckRunner = Callable[[Any, dict[str, Any]], None]


@dataclass(frozen=True)
class BuiltinCheckPlugin:
    id: str
    title: str
    runner: CheckRunner

    def discover(self, context: Any) -> dict[str, Any]:
        return {}

    def check(self, context: Any, discovered: dict[str, Any]) -> list[CheckResult]:
        start = len(context.results)
        self.runner(context, discovered)
        return context.results[start:]


def _checked_env(context: Any) -> dict[str, str]:
    return getattr(context, "_checked_env", {})


def _check_project(context: Any, discovered: dict[str, Any]) -> None:
    check_project(context, discovered)


def _check_discovery(context: Any, discovered: dict[str, Any]) -> None:
    check_discovery(context, discovered)


def _check_coverage(context: Any, discovered: dict[str, Any]) -> None:
    check_coverage_manifest(context, discovered)


def _check_environment(context: Any, discovered: dict[str, Any]) -> None:
    env, env_report = check_env_files(context)
    context._checked_env = env
    context._env_report = env_report
    check_env_values(context, env)


def _check_providers(context: Any, discovered: dict[str, Any]) -> None:
    env = _checked_env(context)
    check_provider_config(context, env)
    check_provider_tools(context, env)


def _check_parsers(context: Any, discovered: dict[str, Any]) -> None:
    check_parsers(context, discovered, _checked_env(context))


def _check_processors(context: Any, discovered: dict[str, Any]) -> None:
    check_processors(context, discovered, _checked_env(context))


def _check_formats(context: Any, discovered: dict[str, Any]) -> None:
    check_format_features(context, discovered, _checked_env(context))


def _check_storage(context: Any, discovered: dict[str, Any]) -> None:
    check_storage_backends(context, _checked_env(context))


def _check_cli(context: Any, discovered: dict[str, Any]) -> None:
    check_cli_manifest(context, discovered)


def _check_exports_api(context: Any, discovered: dict[str, Any]) -> None:
    check_exports_and_api(context, discovered)


def _check_smoke(context: Any, discovered: dict[str, Any]) -> None:
    check_smoke_manifest(context)


BUILTIN_CHECK_PLUGINS: tuple[BuiltinCheckPlugin, ...] = (
    BuiltinCheckPlugin("project", "RAG-Anything repository boundary checks", _check_project),
    BuiltinCheckPlugin("discovery", "RAG-Anything offered surface discovery", _check_discovery),
    BuiltinCheckPlugin("coverage", "Coverage manifest checks", _check_coverage),
    BuiltinCheckPlugin("environment", "Environment and config value checks", _check_environment),
    BuiltinCheckPlugin("providers", "LLM and embedding provider checks", _check_providers),
    BuiltinCheckPlugin("parsers", "Parser availability checks", _check_parsers),
    BuiltinCheckPlugin("processors", "Multimodal processor checks", _check_processors),
    BuiltinCheckPlugin("formats", "Format and converter checks", _check_formats),
    BuiltinCheckPlugin("storage", "LightRAG storage checks", _check_storage),
    BuiltinCheckPlugin("cli", "CLI surface checks", _check_cli),
    BuiltinCheckPlugin("exports_api", "Package exports and public API checks", _check_exports_api),
    BuiltinCheckPlugin("smoke", "Optional smoke-test checks", _check_smoke),
)

__all__ = ["BuiltinCheckPlugin", "BUILTIN_CHECK_PLUGINS", "CheckResult"]
