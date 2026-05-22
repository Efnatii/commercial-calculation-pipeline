#!/usr/bin/env python3
from __future__ import annotations
import argparse
import time
from pathlib import Path
from typing import Any
from wrapper_modules.rag_anything.core.config import as_list, load_config, normalize_names
from wrapper_modules.rag_anything.core.paths import find_project_root, resolve_path
from wrapper_modules.rag_anything.core.models import (
    STATUS_FAIL,
    STATUS_OK,
    STATUS_SKIP,
    STATUS_WARN,
    CheckResult,
    ToolReport,
)
from wrapper_modules.rag_anything.core.reporting import print_report, report_to_dict, write_report
from wrapper_modules.rag_anything.discovery.api import discover_public_api
from wrapper_modules.rag_anything.discovery.cli import discover_cli
from wrapper_modules.rag_anything.discovery.env import discover_env_example, discover_env_surface
from wrapper_modules.rag_anything.discovery.exports import discover_exports
from wrapper_modules.rag_anything.discovery.formats import discover_default_extensions
from wrapper_modules.rag_anything.discovery.parsers import discover_supported_parsers
from wrapper_modules.rag_anything.discovery.processors import discover_processors
from wrapper_modules.rag_anything.discovery.pyproject import discover_pyproject
from wrapper_modules.rag_anything.plugins.registry import get_check_plugins
class Checker:
    def __init__(
        self,
        project_root: Path,
        config_path: Path,
        config: dict[str, Any],
        python_override: str | None = None,
        strict_override: bool = False,
    ) -> None:
        self.project_root = project_root
        self.config_path = config_path
        self.config = config
        self.paths = config.get("paths", {})
        self.execution = config.get("execution", {})
        self.coverage = config.get("coverage", {})
        self.policy = config.get("policy", {})
        self.providers = config.get("providers", {})
        self.commands = config.get("commands", {})
        self.env_groups = config.get("env_groups", {})
        self.env_validation = config.get("env_validation", {})
        self.storage_backends = config.get("storage_backends", {})
        self.cli_manifest = config.get("cli", {})
        self.api_manifest = config.get("api", {})
        self.exports_manifest = config.get("exports", {})
        self.strict = bool(self.policy.get("strict", False) or strict_override)
        self.python = python_override or str(self.execution.get("python", "python"))
        self.timeout = int(self.execution.get("command_timeout_seconds", 20))
        self.results: list[CheckResult] = []
        self.rag_dir = resolve_path(project_root, str(self.paths.get("rag_dir", "RAG-Anything")))
        self.required_parsers = normalize_names(self.policy.get("required_parsers", []))
        self.optional_parsers = normalize_names(self.policy.get("optional_parsers", []))
        self.required_processors = normalize_names(self.policy.get("required_processors", []))
        self.optional_processors = normalize_names(self.policy.get("optional_processors", []))
        self.required_features = normalize_names(self.policy.get("required_format_features", []))
        self.optional_features = normalize_names(self.policy.get("optional_format_features", []))
        self.required_env = {str(item).strip() for item in as_list(self.policy.get("required_env", []))}
        self.secret_env = {str(item).strip().upper() for item in as_list(self.policy.get("secret_env", []))}
        self.placeholders = {
            str(item).strip().strip("'\"").lower()
            for item in as_list(self.policy.get("placeholder_values", []))
        }
    def add(
        self,
        category: str,
        name: str,
        status: str,
        detail: str,
        required: bool = False,
        remediation: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self.strict and status == STATUS_WARN:
            status = STATUS_FAIL
            if remediation:
                remediation = f"{remediation} (strict mode)"
            else:
                remediation = "Strict mode treats this warning as a failure."
        self.results.append(
            CheckResult(
                category=category,
                name=name,
                status=status,
                detail=detail,
                required=required,
                remediation=remediation,
                metadata=metadata or {},
            )
        )
    def required_status(self, condition: bool, required: bool) -> str:
        if condition:
            return STATUS_OK
        return STATUS_FAIL if required else STATUS_WARN
    def configured_env_keys(self) -> set[str]:
        keys: set[str] = set()
        for group in self.env_groups.values():
            if isinstance(group, dict):
                keys.update(str(item).strip() for item in as_list(group.get("keys", [])))
        keys.update(self.required_env)
        keys.update(str(item).strip() for item in as_list(self.policy.get("secret_env", [])))
        for value in self.env_validation.values():
            if isinstance(value, dict):
                keys.update(str(item).strip() for item in value.keys())
            else:
                keys.update(str(item).strip() for item in as_list(value))
        for backend in self.storage_backends.values():
            if isinstance(backend, dict):
                keys.update(str(item).strip() for item in as_list(backend.get("required_keys", [])))
        return {key for key in keys if key}
    def configured_export_symbols(self) -> set[str]:
        symbols: set[str] = set()
        for group in self.exports_manifest.values():
            if isinstance(group, dict):
                symbols.update(str(item).strip() for item in as_list(group.get("symbols", [])))
        return {symbol for symbol in symbols if symbol}
    def configured_api_methods(self) -> set[str]:
        methods: set[str] = set()
        for group in self.api_manifest.values():
            if isinstance(group, dict):
                methods.update(str(item).strip() for item in as_list(group.get("methods", [])))
        return {method for method in methods if method}
    def discover(self) -> dict[str, Any]:
        return {
            "parsers": discover_supported_parsers(self.rag_dir),
            "processors": discover_processors(self.rag_dir),
            "pyproject": discover_pyproject(self.rag_dir),
            "env_example": discover_env_example(self.rag_dir),
            "env_surface": discover_env_surface(self.rag_dir),
            "default_extensions": discover_default_extensions(self.rag_dir),
            "cli": discover_cli(self.rag_dir),
            "exports": discover_exports(self.rag_dir),
            "public_api": discover_public_api(self.rag_dir),
        }
    def run(self) -> ToolReport:
        discovered = self.discover()
        self._checked_env: dict[str, str] = {}
        self._env_report: dict[str, Any] = {}
        for plugin in get_check_plugins():
            plugin.discover(self)
            plugin.check(self, discovered)
        return ToolReport(
            generated_at_epoch=time.time(),
            project_root=str(self.project_root),
            config_path=str(self.config_path),
            rag_dir=str(self.rag_dir),
            strict=self.strict,
            discovered=discovered,
            env=self._env_report,
            results=self.results,
        )
def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="External RAG-Anything tool and configuration checker."
    )
    parser.add_argument(
        "--config",
        default=str(find_project_root() / "configs" / "rag-tool-check.toml"),
        help="Path to TOML or JSON checker config.",
    )
    parser.add_argument(
        "--python",
        default=None,
        help="Python executable used for dependency import checks.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as failures.",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Always exit 0 after writing/printing the report.",
    )
    parser.add_argument(
        "--no-json-report",
        action="store_true",
        help="Do not write the JSON report configured in paths.report_json.",
    )
    return parser
def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    project_root = find_project_root()
    config_path = resolve_path(project_root, args.config)
    try:
        config = load_config(config_path)
        if args.python:
            config.setdefault("execution", {})["python"] = args.python
        checker = Checker(
            project_root=project_root,
            config_path=config_path,
            config=config,
            python_override=args.python,
            strict_override=args.strict,
        )
        report = checker.run()
        print_report(report)
        report_json = config.get("paths", {}).get("report_json")
        if report_json and not args.no_json_report:
            write_report(resolve_path(project_root, str(report_json)), report)
        if args.report_only:
            return 0
        if report.has_failures() or (report.strict and report.has_warnings()):
            return 1
        return 0
    except Exception as exc:
        print(f"rag-anything check error: {exc}", file=sys.stderr)
        return 2
if __name__ == "__main__":
    raise SystemExit(main())
