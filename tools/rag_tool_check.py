#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


STATUS_OK = "OK"
STATUS_WARN = "WARN"
STATUS_FAIL = "FAIL"
STATUS_SKIP = "SKIP"


DEFAULT_CONFIG: dict[str, Any] = {
    "paths": {
        "rag_dir": "RAG-Anything",
        "env_files": [".env", "RAG-Anything/.env"],
        "report_json": "reports/rag-tool-check.json",
    },
    "execution": {
        "python": "python",
        "include_process_env": True,
        "command_timeout_seconds": 20,
        "network_checks": False,
    },
    "policy": {
        "strict": False,
        "required_parsers": ["mineru"],
        "optional_parsers": ["docling", "paddleocr"],
        "required_processors": ["image", "table", "equation"],
        "optional_processors": ["generic"],
        "required_format_features": [],
        "optional_format_features": [
            "office",
            "image",
            "text",
            "markdown",
            "paddleocr_pdf",
        ],
        "selected_parser_required": True,
        "required_env": [
            "LLM_BINDING",
            "LLM_MODEL",
            "LLM_BINDING_HOST",
            "EMBEDDING_BINDING",
            "EMBEDDING_MODEL",
            "EMBEDDING_BINDING_HOST",
        ],
        "secret_env": [
            "OPENAI_API_KEY",
            "LLM_BINDING_API_KEY",
            "EMBEDDING_BINDING_API_KEY",
            "LIGHTRAG_API_KEY",
            "TOKEN_SECRET",
            "POSTGRES_PASSWORD",
            "NEO4J_PASSWORD",
            "MILVUS_TOKEN",
            "QDRANT_API_KEY",
        ],
        "placeholder_values": [
            "",
            "your_api_key",
            "your-secure-api-key-here",
            "your_password",
            "your_username",
            "xxxxxxxx",
            "token-abc123",
        ],
    },
    "providers": {
        "allowed_llm_bindings": [
            "openai",
            "ollama",
            "lollms",
            "azure_openai",
            "lmstudio",
            "vllm",
        ],
        "allowed_embedding_bindings": [
            "openai",
            "ollama",
            "lollms",
            "azure_openai",
            "lmstudio",
            "vllm",
        ],
        "llm_api_key_required_for": ["openai", "azure_openai"],
        "embedding_api_key_required_for": ["openai", "azure_openai"],
    },
    "commands": {
        "mineru": ["mineru", "--version"],
        "libreoffice": [["libreoffice", "--version"], ["soffice", "--version"]],
    },
}


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class CheckResult:
    category: str
    name: str
    status: str
    detail: str
    required: bool = False
    remediation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolReport:
    generated_at_epoch: float
    project_root: str
    config_path: str
    rag_dir: str
    strict: bool
    discovered: dict[str, Any]
    env: dict[str, Any]
    results: list[CheckResult]

    def counts(self) -> dict[str, int]:
        counts = {STATUS_OK: 0, STATUS_WARN: 0, STATUS_FAIL: 0, STATUS_SKIP: 0}
        for result in self.results:
            counts[result.status] = counts.get(result.status, 0) + 1
        return counts

    def has_failures(self) -> bool:
        return any(result.status == STATUS_FAIL for result in self.results)

    def has_warnings(self) -> bool:
        return any(result.status == STATUS_WARN for result in self.results)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "TOML config requires Python 3.11+ or the 'tomli' package. "
            "Alternatively pass a JSON config file."
        ) from exc

    with path.open("rb") as file:
        return tomllib.load(file)


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    if path.suffix.lower() == ".toml":
        loaded = load_toml(path)
    elif path.suffix.lower() == ".json":
        loaded = json.loads(path.read_text(encoding="utf-8"))
    else:
        raise ValueError(f"Unsupported config format: {path.suffix}")
    return deep_merge(DEFAULT_CONFIG, loaded)


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set, frozenset)):
        return list(value)
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if hasattr(value, "__iter__") and not isinstance(value, dict):
        return list(value)
    return [value]


def normalize_names(value: Any) -> set[str]:
    return {str(item).strip().lower() for item in as_list(value) if str(item).strip()}


def resolve_path(project_root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / path


def parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def strip_inline_comment(value: str) -> str:
    in_single = False
    in_double = False
    escaped = False
    output: list[str] = []
    for char in value:
        if escaped:
            output.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            output.append(char)
            continue
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            break
        output.append(char)
    return "".join(output).strip()


def clean_env_value(value: str) -> str:
    value = strip_inline_comment(value.strip())
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_env_file(path: Path, include_commented: bool = False) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            if not include_commented:
                continue
            line = line[1:].strip()
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        values[key] = clean_env_value(value)
    return values


def load_effective_env(
    env_files: list[Path], include_process_env: bool
) -> tuple[dict[str, str], list[str], list[str]]:
    effective: dict[str, str] = {}
    loaded: list[str] = []
    missing: list[str] = []
    for env_file in env_files:
        if env_file.exists():
            effective.update(parse_env_file(env_file))
            loaded.append(str(env_file))
        else:
            missing.append(str(env_file))
    if include_process_env:
        effective.update({key: str(value) for key, value in os.environ.items()})
    return effective, loaded, missing


def is_secret_key(key: str, secret_keys: set[str]) -> bool:
    upper = key.upper()
    if upper in secret_keys:
        return True
    return any(token in upper for token in ("TOKEN", "PASSWORD", "SECRET", "API_KEY"))


def redact_value(key: str, value: str, secret_keys: set[str]) -> str:
    if not is_secret_key(key, secret_keys):
        return value
    if not value:
        return ""
    return "<redacted>"


def is_placeholder(value: str | None, placeholders: set[str]) -> bool:
    if value is None:
        return True
    normalized = value.strip().strip("'\"").lower()
    if normalized in placeholders:
        return True
    return any(token in normalized for token in ("your_", "xxxxxxxx", "<"))


def run_command(
    command: list[str], timeout_seconds: int, cwd: Path | None = None
) -> tuple[bool, str, int | None]:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return False, f"Command not found: {command[0]}", None
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout_seconds}s: {' '.join(command)}", None
    except Exception as exc:  # pragma: no cover - defensive reporting
        return False, f"Command failed to start: {exc}", None

    output = (result.stdout or result.stderr or "").strip()
    if result.returncode == 0:
        return True, output, result.returncode
    return False, output or f"Exit code {result.returncode}", result.returncode


def compact_error_output(text: str) -> str:
    clean = ANSI_RE.sub("", text or "")
    lines = [line.strip() for line in clean.splitlines() if line.strip()]
    if not lines:
        return ""
    for line in reversed(lines):
        if "Error" in line or "Exception" in line or "No module named" in line:
            return line
    return lines[-1]


def run_first_success(
    commands: list[list[str]], timeout_seconds: int
) -> tuple[bool, str, list[str] | None]:
    messages: list[str] = []
    for command in commands:
        ok, output, _ = run_command(command, timeout_seconds)
        if ok:
            return True, output, command
        messages.append(f"{' '.join(command)} -> {output}")
    return False, "; ".join(messages), None


def python_import_check(
    python: str,
    import_statement: str,
    timeout_seconds: int,
    extra_pythonpath: Path | None = None,
) -> tuple[bool, str]:
    code = (
        "import importlib\n"
        f"{import_statement}\n"
        "print('ok')\n"
    )
    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    env["PYTHON_COLORS"] = "0"
    env["TERM"] = "dumb"
    if extra_pythonpath is not None:
        old = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(extra_pythonpath) + (os.pathsep + old if old else "")
    try:
        result = subprocess.run(
            [python, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return False, f"Python executable not found: {python}"
    except subprocess.TimeoutExpired:
        return False, f"Python import check timed out after {timeout_seconds}s"

    if result.returncode == 0:
        return True, (result.stdout or "").strip()
    return False, compact_error_output((result.stderr or result.stdout) or "")


def ast_string_tuple(value: ast.AST) -> list[str]:
    if isinstance(value, (ast.Tuple, ast.List, ast.Set)):
        items: list[str] = []
        for element in value.elts:
            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                items.append(element.value)
        return items
    return []


def ast_string_list(value: ast.AST) -> list[str]:
    if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
        items: list[str] = []
        for item in value.elts:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                items.append(item.value)
        return items
    return []


def first_argument_name(call: ast.Call) -> str:
    for arg in call.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    return ""


def cli_argument_names(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"arguments": [], "choices": {}, "source": str(path)}
    if not path.exists():
        result["error"] = "file not found"
        return result
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError as exc:
        result["error"] = str(exc)
        return result

    arguments: list[str] = []
    choices: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "add_argument":
            continue
        name = first_argument_name(node)
        if not name:
            continue
        normalized = name.split()[0]
        arguments.append(normalized)
        for keyword in node.keywords:
            if keyword.arg == "choices":
                values = ast_string_list(keyword.value)
                if values:
                    choices[normalized] = values
    result["arguments"] = arguments
    result["choices"] = choices
    return result


def discover_cli(rag_dir: Path) -> dict[str, Any]:
    return {
        "parser": cli_argument_names(rag_dir / "raganything" / "parser.py"),
        "batch_parser": cli_argument_names(rag_dir / "raganything" / "batch_parser.py"),
        "enhanced_markdown": cli_argument_names(
            rag_dir / "raganything" / "enhanced_markdown.py"
        ),
    }


def discover_env_surface(rag_dir: Path) -> dict[str, Any]:
    env_example = rag_dir / "env.example"
    documented: dict[str, dict[str, Any]] = {}
    section = "unsectioned"
    if env_example.exists():
        for line_no, raw_line in enumerate(
            env_example.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            stripped = raw_line.strip()
            if stripped.startswith("###"):
                title = stripped.strip("#").strip()
                if title and not set(title) <= {"-"}:
                    section = title
                continue
            line = stripped
            if line.startswith("#"):
                line = line[1:].strip()
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            match = re.match(r"^([A-Z_][A-Z0-9_]*)\s*=", line)
            if match:
                key = match.group(1)
                documented.setdefault(
                    key, {"sections": [], "lines": [], "source": str(env_example)}
                )
                documented[key]["sections"].append(section)
                documented[key]["lines"].append(line_no)

    code_keys: dict[str, list[str]] = {}
    code_paths = (
        list((rag_dir / "raganything").rglob("*.py"))
        + list((rag_dir / "examples").rglob("*.py"))
        + list((rag_dir / "reproduce").rglob("*.py"))
    )
    patterns = [
        r'get_env_value\("([A-Z0-9_]+)"',
        r'os\.getenv\("([A-Z0-9_]+)"',
        r'os\.environ\.get\("([A-Z0-9_]+)"',
    ]
    for path in code_paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in patterns:
            for key in re.findall(pattern, text):
                code_keys.setdefault(key, []).append(str(path))

    return {
        "documented": documented,
        "code": {key: sorted(set(paths)) for key, paths in code_keys.items()},
        "all_keys": sorted(set(documented) | set(code_keys)),
    }


def discover_exports(rag_dir: Path) -> dict[str, Any]:
    init_py = rag_dir / "raganything" / "__init__.py"
    result: dict[str, Any] = {"symbols": [], "source": str(init_py)}
    if not init_py.exists():
        result["error"] = "file not found"
        return result
    try:
        tree = ast.parse(init_py.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError as exc:
        result["error"] = str(exc)
        return result

    symbols: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    symbols.extend(ast_string_list(node.value))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "__all__"
                and node.func.attr == "extend"
                and node.args
            ):
                symbols.extend(ast_string_list(node.args[0]))
    result["symbols"] = sorted(set(symbols))
    return result


def discover_public_api(rag_dir: Path) -> dict[str, Any]:
    files = [
        "raganything.py",
        "processor.py",
        "query.py",
        "batch.py",
        "parser.py",
        "batch_parser.py",
        "enhanced_markdown.py",
        "prompt_manager.py",
    ]
    ignored = {"main"}
    result: dict[str, list[str]] = {}
    for filename in files:
        path = rag_dir / "raganything" / filename
        if not path.exists():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        methods: set[str] = set()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_") and node.name not in ignored:
                    methods.add(node.name)
            elif isinstance(node, ast.ClassDef):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not child.name.startswith("_") and child.name not in ignored:
                            methods.add(child.name)
        if methods:
            result[filename] = sorted(methods)
    return result


def discover_supported_parsers(rag_dir: Path) -> dict[str, Any]:
    parser_py = rag_dir / "raganything" / "parser.py"
    discovered = {
        "names": [],
        "custom_registry": False,
        "source": str(parser_py),
        "error": "",
    }
    if not parser_py.exists():
        discovered["error"] = "parser.py not found"
        return discovered

    text = parser_py.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "SUPPORTED_PARSERS":
                        discovered["names"] = ast_string_tuple(node.value)
            elif isinstance(node, ast.FunctionDef) and node.name == "register_parser":
                discovered["custom_registry"] = True
    except SyntaxError as exc:
        discovered["error"] = f"Unable to parse parser.py: {exc}"

    if not discovered["names"]:
        matches = re.findall(r'"(mineru|docling|paddleocr)"', text)
        discovered["names"] = sorted(set(matches))
    return discovered


def discover_processors(rag_dir: Path) -> dict[str, Any]:
    modal_py = rag_dir / "raganything" / "modalprocessors.py"
    utils_py = rag_dir / "raganything" / "utils.py"
    processors: dict[str, Any] = {}

    if modal_py.exists():
        text = modal_py.read_text(encoding="utf-8", errors="replace")
        for class_name in re.findall(r"^class\s+([A-Za-z]+ModalProcessor)\b", text, re.M):
            name = class_name.replace("ModalProcessor", "").lower()
            if name == "base":
                continue
            processors[name] = {"class": class_name, "supports": []}

    if utils_py.exists():
        try:
            tree = ast.parse(utils_py.read_text(encoding="utf-8", errors="replace"))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "get_processor_supports":
                    for child in ast.walk(node):
                        if not isinstance(child, ast.Assign):
                            continue
                        if not any(
                            isinstance(target, ast.Name) and target.id == "supports_map"
                            for target in child.targets
                        ):
                            continue
                        if not isinstance(child.value, ast.Dict):
                            continue
                        for key_node, value_node in zip(child.value.keys, child.value.values):
                            if not isinstance(key_node, ast.Constant):
                                continue
                            key = str(key_node.value)
                            supports: list[str] = []
                            if isinstance(value_node, ast.List):
                                for item in value_node.elts:
                                    if isinstance(item, ast.Constant):
                                        supports.append(str(item.value))
                            processors.setdefault(key, {"class": "", "supports": []})
                            processors[key]["supports"] = supports
        except SyntaxError:
            pass
    return processors


def discover_pyproject(rag_dir: Path) -> dict[str, Any]:
    pyproject = rag_dir / "pyproject.toml"
    result: dict[str, Any] = {
        "path": str(pyproject),
        "requires_python": "",
        "dependencies": [],
        "optional_dependencies": {},
        "error": "",
    }
    if not pyproject.exists():
        result["error"] = "pyproject.toml not found"
        return result
    try:
        data = load_toml(pyproject)
        project = data.get("project", {})
        result["requires_python"] = str(project.get("requires-python", ""))
        result["dependencies"] = list(project.get("dependencies", []))
        result["optional_dependencies"] = dict(project.get("optional-dependencies", {}))
    except Exception as exc:
        result["error"] = str(exc)
    return result


def discover_env_example(rag_dir: Path) -> dict[str, Any]:
    env_example = rag_dir / "env.example"
    values = parse_env_file(env_example, include_commented=True)
    return {
        "path": str(env_example),
        "exists": env_example.exists(),
        "keys": sorted(values),
    }


def discover_default_extensions(rag_dir: Path) -> list[str]:
    config_py = rag_dir / "raganything" / "config.py"
    if not config_py.exists():
        return []
    text = config_py.read_text(encoding="utf-8", errors="replace")
    match = re.search(r'"(\.pdf,[^"]+\.md)"', text)
    if not match:
        return []
    return [item.strip().lower() for item in match.group(1).split(",") if item.strip()]


def parse_min_python(requires_python: str) -> tuple[int, int] | None:
    match = re.search(r">=\s*(\d+)\.(\d+)", requires_python)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def has_valid_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def detect_mcp_artifacts(project_root: Path) -> list[str]:
    names = {"mcp.json", ".mcp.json", "mcp.config.json", "plugin.json"}
    found: list[str] = []
    ignored_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv"}
    for root, dirs, files in os.walk(project_root):
        root_path = Path(root)
        dirs[:] = [item for item in dirs if item not in ignored_dirs]
        if ".codex-plugin" in dirs:
            found.append(str(root_path / ".codex-plugin"))
        for filename in files:
            if filename in names:
                found.append(str(root_path / filename))
    return found


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

    def check_project(self, discovered: dict[str, Any]) -> None:
        if self.rag_dir.exists():
            self.add("project", "rag_dir", STATUS_OK, f"Found {self.rag_dir}")
        else:
            self.add(
                "project",
                "rag_dir",
                STATUS_FAIL,
                f"Missing RAG-Anything directory: {self.rag_dir}",
                required=True,
                remediation="Initialize submodules: git submodule update --init --recursive",
            )
            return

        ok, output, _ = run_command(["git", "-C", str(self.rag_dir), "rev-parse", "--short", "HEAD"], self.timeout)
        if ok:
            self.add("project", "rag_revision", STATUS_OK, f"RAG-Anything revision {output}")
        else:
            self.add("project", "rag_revision", STATUS_WARN, output)

        rel = os.path.relpath(self.rag_dir, self.project_root).replace("\\", "/")
        ok, output, _ = run_command(["git", "ls-files", "--stage", rel], self.timeout, self.project_root)
        if ok and output.startswith("160000 "):
            self.add("project", "gitlink", STATUS_OK, f"{rel} is tracked as a git submodule")
        elif ok and output:
            self.add("project", "gitlink", STATUS_WARN, f"{rel} is tracked, but not as gitlink: {output}")
        else:
            self.add("project", "gitlink", STATUS_WARN, f"{rel} is not tracked as a git submodule")

        pyproject = discovered.get("pyproject", {})
        minimum = parse_min_python(str(pyproject.get("requires_python", "")))
        if minimum:
            current = sys.version_info[:2]
            if current >= minimum:
                self.add(
                    "runtime",
                    "python_version",
                    STATUS_OK,
                    f"Python {current[0]}.{current[1]} satisfies >= {minimum[0]}.{minimum[1]}",
                )
            else:
                self.add(
                    "runtime",
                    "python_version",
                    STATUS_FAIL,
                    f"Python {current[0]}.{current[1]} does not satisfy >= {minimum[0]}.{minimum[1]}",
                    required=True,
                )

        mcp_artifacts = detect_mcp_artifacts(self.project_root)
        if mcp_artifacts:
            self.add(
                "integration",
                "codex_mcp_plugin_boundary",
                STATUS_WARN,
                "Potential MCP/plugin artifacts found in repository",
                metadata={"paths": mcp_artifacts},
            )
        else:
            self.add(
                "integration",
                "codex_mcp_plugin_boundary",
                STATUS_OK,
                "No repo-local MCP/plugin registration artifacts found",
            )

    def check_discovery(self, discovered: dict[str, Any]) -> None:
        parser_info = discovered.get("parsers", {})
        parser_names = parser_info.get("names") or []
        if parser_names:
            self.add("discover", "parsers", STATUS_OK, ", ".join(parser_names))
        else:
            self.add(
                "discover",
                "parsers",
                STATUS_FAIL,
                parser_info.get("error") or "No parser names discovered",
                required=True,
            )

        if parser_info.get("custom_registry"):
            self.add(
                "discover",
                "custom_parser_registry",
                STATUS_OK,
                "RAG-Anything exposes register_parser/unregister_parser APIs",
            )

        processors = discovered.get("processors", {})
        if processors:
            self.add("discover", "modal_processors", STATUS_OK, ", ".join(sorted(processors)))
        else:
            self.add("discover", "modal_processors", STATUS_WARN, "No modal processors discovered")

        extras = discovered.get("pyproject", {}).get("optional_dependencies", {})
        if extras:
            self.add("discover", "optional_extras", STATUS_OK, ", ".join(sorted(extras)))
        else:
            self.add("discover", "optional_extras", STATUS_WARN, "No optional extras discovered")

        env_example = discovered.get("env_example", {})
        if env_example.get("exists"):
            self.add(
                "discover",
                "env_example",
                STATUS_OK,
                f"Found {len(env_example.get('keys', []))} documented env keys",
            )
        else:
            self.add("discover", "env_example", STATUS_WARN, "RAG-Anything/env.example is missing")

        env_surface = discovered.get("env_surface", {})
        env_keys = env_surface.get("all_keys", [])
        if env_keys:
            self.add("discover", "env_surface", STATUS_OK, f"Found {len(env_keys)} env keys across env.example/code")

        cli = discovered.get("cli", {})
        if cli:
            parts = [
                f"{name}:{len(info.get('arguments', []))}"
                for name, info in sorted(cli.items())
            ]
            self.add("discover", "cli_surface", STATUS_OK, ", ".join(parts))

        exports = discovered.get("exports", {}).get("symbols", [])
        if exports:
            self.add("discover", "package_exports", STATUS_OK, ", ".join(exports))

    def check_coverage_manifest(self, discovered: dict[str, Any]) -> None:
        if not self.coverage.get("require_full_coverage", False):
            self.add("coverage", "manifest", STATUS_SKIP, "Full coverage enforcement is disabled")
            return

        parser_names = normalize_names(discovered.get("parsers", {}).get("names", []))
        configured_parsers = self.required_parsers | self.optional_parsers
        missing_parsers = sorted(parser_names - configured_parsers)
        self.add(
            "coverage",
            "parsers",
            STATUS_OK if not missing_parsers else STATUS_FAIL,
            "All discovered parsers are listed" if not missing_parsers else f"Missing parser coverage: {', '.join(missing_parsers)}",
            required=True,
        )

        processor_names = normalize_names(discovered.get("processors", {}).keys())
        configured_processors = self.required_processors | self.optional_processors
        missing_processors = sorted(processor_names - configured_processors)
        self.add(
            "coverage",
            "processors",
            STATUS_OK if not missing_processors else STATUS_FAIL,
            "All discovered processors are listed" if not missing_processors else f"Missing processor coverage: {', '.join(missing_processors)}",
            required=True,
        )

        extras = normalize_names(discovered.get("pyproject", {}).get("optional_dependencies", {}).keys())
        configured_extras = normalize_names(self.policy.get("required_optional_extras", [])) | normalize_names(
            self.policy.get("optional_extras", [])
        )
        missing_extras = sorted(extras - configured_extras)
        self.add(
            "coverage",
            "optional_extras",
            STATUS_OK if not missing_extras else STATUS_FAIL,
            "All optional extras are listed" if not missing_extras else f"Missing optional extra coverage: {', '.join(missing_extras)}",
            required=True,
        )

        if self.coverage.get("require_full_env_coverage", False):
            discovered_env = set(discovered.get("env_surface", {}).get("all_keys", []))
            configured_env = self.configured_env_keys()
            missing_env = sorted(discovered_env - configured_env)
            self.add(
                "coverage",
                "env_keys",
                STATUS_OK if not missing_env else STATUS_FAIL,
                f"All {len(discovered_env)} discovered env keys are grouped"
                if not missing_env
                else f"Missing env key coverage: {', '.join(missing_env)}",
                required=True,
            )

        if self.coverage.get("require_full_cli_coverage", False):
            for cli_name, info in sorted(discovered.get("cli", {}).items()):
                discovered_args = set(info.get("arguments", []))
                configured_args = set(as_list(self.cli_manifest.get(cli_name, {}).get("arguments", [])))
                missing_args = sorted(discovered_args - configured_args)
                self.add(
                    "coverage",
                    f"cli:{cli_name}",
                    STATUS_OK if not missing_args else STATUS_FAIL,
                    f"All {len(discovered_args)} CLI args are listed"
                    if not missing_args
                    else f"Missing CLI arg coverage: {', '.join(missing_args)}",
                    required=True,
                )

        if self.coverage.get("require_full_export_coverage", False):
            discovered_exports = set(discovered.get("exports", {}).get("symbols", []))
            configured_exports = self.configured_export_symbols()
            missing_exports = sorted(discovered_exports - configured_exports)
            self.add(
                "coverage",
                "exports",
                STATUS_OK if not missing_exports else STATUS_FAIL,
                "All package exports are listed" if not missing_exports else f"Missing export coverage: {', '.join(missing_exports)}",
                required=True,
            )

        if self.coverage.get("require_full_api_coverage", False):
            discovered_methods = {
                method
                for methods in discovered.get("public_api", {}).values()
                for method in methods
            }
            configured_methods = self.configured_api_methods()
            missing_methods = sorted(discovered_methods - configured_methods)
            self.add(
                "coverage",
                "public_api",
                STATUS_OK if not missing_methods else STATUS_FAIL,
                f"All {len(discovered_methods)} public methods are listed"
                if not missing_methods
                else f"Missing public API coverage: {', '.join(missing_methods)}",
                required=True,
            )

    def check_env_files(self) -> tuple[dict[str, str], dict[str, Any]]:
        env_paths = [
            resolve_path(self.project_root, str(item))
            for item in as_list(self.paths.get("env_files", []))
        ]
        effective_env, loaded, missing = load_effective_env(
            env_paths,
            bool(self.execution.get("include_process_env", True)),
        )
        if loaded:
            self.add("config", "env_files", STATUS_OK, f"Loaded {', '.join(loaded)}")
        else:
            self.add(
                "config",
                "env_files",
                STATUS_WARN,
                "No configured .env files were found; process environment and RAG defaults will be used",
            )
        for missing_path in missing:
            self.add("config", "env_file_missing", STATUS_SKIP, missing_path)
        configured_env = self.configured_env_keys()
        redacted = {
            key: redact_value(key, value, self.secret_env)
            for key, value in sorted(effective_env.items())
            if key in configured_env
        }
        env_report = {"loaded_files": loaded, "missing_files": missing, "effective_subset": redacted}
        return effective_env, env_report

    def check_env_values(self, env: dict[str, str]) -> None:
        for key in sorted(self.required_env):
            value = env.get(key)
            if value is None or value == "":
                self.add(
                    "config",
                    f"env:{key}",
                    STATUS_FAIL,
                    "Required env var is not set",
                    required=True,
                    remediation=f"Set {key} in .env or remove it from policy.required_env.",
                )
            elif is_placeholder(value, self.placeholders):
                self.add(
                    "config",
                    f"env:{key}",
                    STATUS_FAIL,
                    "Required env var still contains a placeholder value",
                    required=True,
                    remediation=f"Replace placeholder value for {key}.",
                )
            else:
                self.add("config", f"env:{key}", STATUS_OK, "Set")

        for group_name, group in sorted(self.env_groups.items()):
            if not isinstance(group, dict):
                continue
            keys = [str(item).strip() for item in as_list(group.get("keys", [])) if str(item).strip()]
            present = [key for key in keys if key in env and env.get(key) not in {None, ""}]
            required = bool(group.get("required", False))
            if required and len(present) < len(keys):
                missing = sorted(set(keys) - set(present))
                self.add(
                    "config",
                    f"env_group:{group_name}",
                    STATUS_FAIL,
                    f"{len(present)}/{len(keys)} keys set; missing {', '.join(missing)}",
                    required=True,
                )
            else:
                status = STATUS_OK if present else STATUS_SKIP
                detail = f"{len(present)}/{len(keys)} keys set"
                if group.get("description"):
                    detail = f"{detail} - {group.get('description')}"
                self.add("config", f"env_group:{group_name}", status, detail)

        parser = env.get("PARSER", "mineru").strip().lower()
        if parser not in {"mineru", "docling", "paddleocr"}:
            self.add(
                "config",
                "PARSER",
                STATUS_FAIL,
                f"Unsupported parser '{parser}'",
                required=True,
                remediation="Use one of: mineru, docling, paddleocr.",
            )
        else:
            self.add("config", "PARSER", STATUS_OK, parser)

        method = env.get("PARSE_METHOD", "auto").strip().lower()
        if method not in {"auto", "ocr", "txt"}:
            self.add(
                "config",
                "PARSE_METHOD",
                STATUS_FAIL,
                f"Unsupported parse method '{method}'",
                required=True,
                remediation="Use one of: auto, ocr, txt.",
            )
        else:
            self.add("config", "PARSE_METHOD", STATUS_OK, method)

        enum_config = self.env_validation.get("enums", {})
        for key, choices in sorted(enum_config.items()):
            if key not in env:
                continue
            allowed = {str(item) for item in as_list(choices)}
            value = str(env[key]).strip()
            if value not in allowed and value.lower() not in {item.lower() for item in allowed}:
                self.add("config", key, STATUS_FAIL, f"Expected one of {sorted(allowed)}, got '{value}'")
            else:
                self.add("config", key, STATUS_OK, value)

        for key in sorted(str(item) for item in as_list(self.env_validation.get("booleans", []))):
            if key not in env:
                continue
            normalized = str(env[key]).strip().lower()
            if normalized not in {"1", "0", "true", "false", "yes", "no", "y", "n", "on", "off"}:
                self.add("config", key, STATUS_FAIL, f"Expected boolean, got '{env[key]}'")

        for key in sorted(str(item) for item in as_list(self.env_validation.get("urls", []))):
            if key not in env or not str(env[key]).strip():
                continue
            value = str(env[key]).strip()
            parsed = urlparse(value)
            if key == "REDIS_URI":
                valid = parsed.scheme in {"redis", "rediss"} and bool(parsed.netloc)
            elif key == "NEO4J_URI":
                valid = parsed.scheme in {"neo4j", "neo4j+s", "bolt", "bolt+s"} and bool(parsed.netloc)
            elif key == "MILVUS_URI":
                valid = (parsed.scheme in {"http", "https", "tcp"} and bool(parsed.netloc)) or value.startswith("./")
            else:
                valid = has_valid_url(value)
            self.add("config", key, STATUS_OK if valid else STATUS_WARN, "URL syntax looks valid" if valid else f"Unexpected URL/URI: {value}")

        for key in sorted(str(item) for item in as_list(self.env_validation.get("comma_lists", []))):
            if key not in env:
                continue
            values = [item.strip() for item in str(env[key]).split(",") if item.strip()]
            status = STATUS_OK if values else STATUS_WARN
            self.add("config", key, status, f"{len(values)} item(s)")

        numeric_minimums = self.env_validation.get("numeric_minimums", {})
        for key, minimum in numeric_minimums.items():
            if key not in env:
                continue
            try:
                value = int(str(env[key]))
                minimum_value = int(minimum)
            except ValueError:
                self.add("config", key, STATUS_FAIL, f"Expected integer, got '{env[key]}'")
                continue
            if value < minimum_value:
                self.add("config", key, STATUS_FAIL, f"Expected >= {minimum_value}, got {value}")
            else:
                self.add("config", key, STATUS_OK, str(value))

        numeric_ranges = self.env_validation.get("numeric_ranges", {})
        for key, bounds in numeric_ranges.items():
            if key not in env:
                continue
            values = as_list(bounds)
            if len(values) != 2:
                continue
            try:
                value = float(str(env[key]))
                low = float(values[0])
                high = float(values[1])
            except ValueError:
                self.add("config", key, STATUS_FAIL, f"Expected number, got '{env[key]}'")
                continue
            status = STATUS_OK if low <= value <= high else STATUS_FAIL
            self.add("config", key, status, f"{value} in range [{low}, {high}]" if status == STATUS_OK else f"Expected [{low}, {high}], got {value}")

        for pair in as_list(self.env_validation.get("paired", [])):
            items = as_list(pair)
            if len(items) != 2:
                continue
            left, right = str(items[0]), str(items[1])
            has_left = bool(env.get(left))
            has_right = bool(env.get(right))
            if has_left != has_right:
                self.add(
                    "config",
                    "public_asset_mapping",
                    STATUS_FAIL,
                    f"{left} and {right} must be set together",
                    required=True,
                )
            elif has_left and has_right:
                self.add("config", "public_asset_mapping", STATUS_OK, "Configured")

    def check_provider_config(self, env: dict[str, str]) -> None:
        allowed_llm = normalize_names(self.providers.get("allowed_llm_bindings", []))
        allowed_embedding = normalize_names(self.providers.get("allowed_embedding_bindings", []))
        llm_key_required = normalize_names(self.providers.get("llm_api_key_required_for", []))
        embedding_key_required = normalize_names(self.providers.get("embedding_api_key_required_for", []))

        llm_binding = env.get("LLM_BINDING")
        if llm_binding:
            normalized = llm_binding.strip().lower()
            if normalized not in allowed_llm:
                self.add("provider", "LLM_BINDING", STATUS_FAIL, f"Unknown LLM binding '{llm_binding}'")
            else:
                self.add("provider", "LLM_BINDING", STATUS_OK, normalized)
            host = env.get("LLM_BINDING_HOST")
            if host and normalized in {"openai", "azure_openai", "lmstudio", "vllm"} and not has_valid_url(host):
                self.add("provider", "LLM_BINDING_HOST", STATUS_WARN, f"Host is not an HTTP(S) URL: {host}")
            if normalized in llm_key_required:
                key = env.get("LLM_BINDING_API_KEY") or env.get("OPENAI_API_KEY")
                status = self.required_status(not is_placeholder(key, self.placeholders), True)
                self.add(
                    "provider",
                    "LLM_API_KEY",
                    status,
                    "Present" if status == STATUS_OK else f"Missing or placeholder API key for {normalized}",
                    required=True,
                )

        embedding_binding = env.get("EMBEDDING_BINDING")
        if embedding_binding:
            normalized = embedding_binding.strip().lower()
            if normalized not in allowed_embedding:
                self.add("provider", "EMBEDDING_BINDING", STATUS_FAIL, f"Unknown embedding binding '{embedding_binding}'")
            else:
                self.add("provider", "EMBEDDING_BINDING", STATUS_OK, normalized)
            host = env.get("EMBEDDING_BINDING_HOST")
            if host and normalized in {"openai", "azure_openai", "ollama", "lmstudio", "vllm"} and not has_valid_url(host):
                self.add("provider", "EMBEDDING_BINDING_HOST", STATUS_WARN, f"Host is not an HTTP(S) URL: {host}")
            if normalized in embedding_key_required:
                key = env.get("EMBEDDING_BINDING_API_KEY") or env.get("OPENAI_API_KEY")
                status = self.required_status(not is_placeholder(key, self.placeholders), True)
                self.add(
                    "provider",
                    "EMBEDDING_API_KEY",
                    status,
                    "Present" if status == STATUS_OK else f"Missing or placeholder API key for {normalized}",
                    required=True,
                )

    def check_parsers(self, discovered: dict[str, Any], env: dict[str, str]) -> None:
        parser_names = [str(name).lower() for name in discovered.get("parsers", {}).get("names", [])]
        selected = env.get("PARSER", "mineru").strip().lower()
        required = set(self.required_parsers)
        if self.policy.get("selected_parser_required", True):
            required.add(selected)

        for requested in sorted(required):
            if requested not in parser_names:
                self.add(
                    "parser",
                    requested,
                    STATUS_FAIL,
                    "Required parser is not offered by this RAG-Anything revision",
                    required=True,
                )

        for parser_name in parser_names:
            is_required = parser_name in required
            if parser_name == "mineru":
                command = as_list(self.commands.get("mineru", ["mineru", "--version"]))
                ok, output, _ = run_command([str(item) for item in command], self.timeout)
                self.add(
                    "parser",
                    "mineru",
                    self.required_status(ok, is_required),
                    output if output else "mineru command is available",
                    required=is_required,
                    remediation="Install with: pip install -U 'mineru[core]'",
                )
            elif parser_name == "docling":
                ok, output = python_import_check(
                    self.python,
                    "from docling.document_converter import DocumentConverter  # noqa",
                    self.timeout,
                )
                self.add(
                    "parser",
                    "docling",
                    self.required_status(ok, is_required),
                    "docling Python package import works" if ok else output,
                    required=is_required,
                    remediation="Install with: pip install docling",
                )
            elif parser_name == "paddleocr":
                ok, output = python_import_check(self.python, "import paddleocr  # noqa", self.timeout)
                self.add(
                    "parser",
                    "paddleocr",
                    self.required_status(ok, is_required),
                    "paddleocr import works" if ok else output,
                    required=is_required,
                    remediation="Install with: pip install -e RAG-Anything[paddleocr], then install paddlepaddle.",
                )
                pdf_required = "paddleocr_pdf" in self.required_features or is_required
                ok_pdf, output_pdf = python_import_check(self.python, "import pypdfium2  # noqa", self.timeout)
                self.add(
                    "parser",
                    "paddleocr_pdf_renderer",
                    self.required_status(ok_pdf, pdf_required),
                    "pypdfium2 import works" if ok_pdf else output_pdf,
                    required=pdf_required,
                    remediation="Install with: pip install pypdfium2",
                )
                ok_paddle, output_paddle = python_import_check(self.python, "import paddle  # noqa", self.timeout)
                self.add(
                    "parser",
                    "paddlepaddle_runtime",
                    self.required_status(ok_paddle, is_required),
                    "paddle import works" if ok_paddle else output_paddle,
                    required=is_required,
                    remediation="Install PaddlePaddle from https://www.paddlepaddle.org.cn/install/quick",
                )

    def check_processors(self, discovered: dict[str, Any], env: dict[str, str]) -> None:
        processors: dict[str, Any] = discovered.get("processors", {})
        env_flags = {
            "image": ("ENABLE_IMAGE_PROCESSING", True),
            "table": ("ENABLE_TABLE_PROCESSING", True),
            "equation": ("ENABLE_EQUATION_PROCESSING", True),
            "generic": (None, True),
        }

        for name in sorted(set(processors) | self.required_processors | self.optional_processors):
            is_required = name in self.required_processors
            if name not in processors:
                self.add(
                    "processor",
                    name,
                    STATUS_FAIL if is_required else STATUS_WARN,
                    "Processor was expected but not discovered",
                    required=is_required,
                )
                continue

            flag, default_enabled = env_flags.get(name, (None, True))
            enabled = default_enabled if flag is None else parse_bool(env.get(flag), default_enabled)
            if not enabled:
                self.add(
                    "processor",
                    name,
                    STATUS_FAIL if is_required else STATUS_WARN,
                    f"Discovered {processors[name].get('class')}, but disabled by {flag}",
                    required=is_required,
                )
            else:
                supports = processors[name].get("supports") or []
                detail = processors[name].get("class") or name
                if supports:
                    detail = f"{detail}: {', '.join(supports)}"
                self.add("processor", name, STATUS_OK, detail, required=is_required)

        if parse_bool(env.get("ENABLE_IMAGE_PROCESSING"), True):
            if not env.get("VISION_MODEL") and not env.get("LLM_MODEL"):
                self.add(
                    "processor",
                    "image_model_hint",
                    STATUS_WARN,
                    "Image processing is enabled, but neither VISION_MODEL nor LLM_MODEL is set in checked env",
                )

    def configured_extensions(self, discovered: dict[str, Any], env: dict[str, str]) -> set[str]:
        raw = env.get("SUPPORTED_FILE_EXTENSIONS")
        if raw:
            return {item.strip().lower() for item in raw.split(",") if item.strip()}
        return set(discovered.get("default_extensions") or [])

    def check_format_features(self, discovered: dict[str, Any], env: dict[str, str]) -> None:
        extensions = self.configured_extensions(discovered, env)
        if extensions:
            self.add("formats", "supported_extensions", STATUS_OK, ", ".join(sorted(extensions)))
        else:
            self.add("formats", "supported_extensions", STATUS_WARN, "No supported extensions discovered")

        feature_requirements: dict[str, bool] = {
            name: True for name in self.required_features
        }
        for name in self.optional_features:
            feature_requirements.setdefault(name, False)

        extended_image_ext = {".bmp", ".tiff", ".tif", ".gif", ".webp"}
        office_ext = {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"}
        text_ext = {".txt", ".md"}

        if "image" in feature_requirements or extensions & extended_image_ext:
            required = bool(feature_requirements.get("image", False))
            ok, output = python_import_check(self.python, "import PIL  # noqa", self.timeout)
            self.add(
                "formats",
                "image_extra",
                self.required_status(ok, required),
                "Pillow import works" if ok else output,
                required=required,
                remediation="Install with: pip install 'raganything[image]'",
            )

        if "text" in feature_requirements or extensions & text_ext:
            required = bool(feature_requirements.get("text", False))
            ok, output = python_import_check(self.python, "import reportlab  # noqa", self.timeout)
            self.add(
                "formats",
                "text_extra",
                self.required_status(ok, required),
                "reportlab import works" if ok else output,
                required=required,
                remediation="Install with: pip install 'raganything[text]'",
            )

        if "office" in feature_requirements or extensions & office_ext:
            required = bool(feature_requirements.get("office", False))
            command_config = self.commands.get("libreoffice", [["libreoffice", "--version"], ["soffice", "--version"]])
            commands = [[str(part) for part in as_list(command)] for command in as_list(command_config)]
            ok, output, command = run_first_success(commands, self.timeout)
            detail = output if ok else "LibreOffice/soffice not found"
            if ok and command:
                detail = f"{' '.join(command)} -> {output}"
            self.add(
                "formats",
                "office_conversion",
                self.required_status(ok, required),
                detail,
                required=required,
                remediation="Install LibreOffice and ensure libreoffice or soffice is on PATH.",
            )

        if "markdown" in feature_requirements:
            required = bool(feature_requirements.get("markdown", False))
            for module in ("markdown", "weasyprint", "pygments"):
                ok, output = python_import_check(self.python, f"import {module}  # noqa", self.timeout)
                self.add(
                    "formats",
                    f"markdown_extra:{module}",
                    self.required_status(ok, required),
                    f"{module} import works" if ok else output,
                    required=required,
                    remediation="Install with: pip install 'raganything[markdown]'",
                )

    def check_cli_manifest(self, discovered: dict[str, Any]) -> None:
        for cli_name, manifest in sorted(self.cli_manifest.items()):
            if not isinstance(manifest, dict):
                continue
            info = discovered.get("cli", {}).get(cli_name, {})
            if not info:
                self.add("cli", cli_name, STATUS_WARN, "CLI source was not discovered")
                continue
            self.add(
                "cli",
                cli_name,
                STATUS_OK,
                f"{manifest.get('module', cli_name)} exposes {len(info.get('arguments', []))} argument(s)",
            )
            choices_by_arg = info.get("choices", {})
            for arg_name, discovered_choices in sorted(choices_by_arg.items()):
                manifest_key = arg_name.lstrip("-").replace("-", "_") + "_choices"
                configured_choices = as_list(manifest.get(manifest_key, []))
                if not configured_choices:
                    self.add(
                        "cli",
                        f"{cli_name}:{arg_name}:choices",
                        STATUS_WARN,
                        f"Choices discovered but not declared in config: {', '.join(discovered_choices)}",
                    )
                    continue
                missing = sorted(set(discovered_choices) - {str(item) for item in configured_choices})
                self.add(
                    "cli",
                    f"{cli_name}:{arg_name}:choices",
                    STATUS_OK if not missing else STATUS_FAIL,
                    "Choices covered" if not missing else f"Missing choices: {', '.join(missing)}",
                    required=bool(missing),
                )

            for tool_name in as_list(manifest.get("optional_tools", [])):
                command = self.commands.get(str(tool_name), [str(tool_name), "--version"])
                ok, output, _ = run_command([str(item) for item in as_list(command)], self.timeout)
                self.add(
                    "cli",
                    f"optional_tool:{tool_name}",
                    STATUS_OK if ok else STATUS_WARN,
                    output if output else f"{tool_name} command available",
                    remediation=f"Install {tool_name} if you need this CLI method.",
                )

    def check_exports_and_api(self, discovered: dict[str, Any]) -> None:
        discovered_exports = set(discovered.get("exports", {}).get("symbols", []))
        for group_name, group in sorted(self.exports_manifest.items()):
            if not isinstance(group, dict):
                continue
            symbols = {str(item) for item in as_list(group.get("symbols", []))}
            required = bool(group.get("required", False))
            missing = sorted(symbols - discovered_exports)
            self.add(
                "exports",
                group_name,
                self.required_status(not missing, required),
                "All symbols discovered" if not missing else f"Missing exported symbols: {', '.join(missing)}",
                required=required,
            )

        discovered_methods = {
            method
            for methods in discovered.get("public_api", {}).values()
            for method in methods
        }
        for group_name, group in sorted(self.api_manifest.items()):
            if not isinstance(group, dict):
                continue
            methods = {str(item) for item in as_list(group.get("methods", []))}
            present = sorted(methods & discovered_methods)
            missing = sorted(methods - discovered_methods)
            status = STATUS_OK if not missing else STATUS_WARN
            self.add(
                "api",
                group_name,
                status,
                f"{len(present)}/{len(methods)} configured method(s) discovered"
                if not missing
                else f"Missing configured method(s): {', '.join(missing)}",
            )

    def check_storage_backends(self, env: dict[str, str]) -> None:
        declared = [str(item) for item in as_list(self.storage_backends.get("declared", []))]
        if declared:
            self.add("storage", "declared_backends", STATUS_OK, ", ".join(declared))

        selector_values = [
            str(env.get(key, ""))
            for key in (
                "LIGHTRAG_KV_STORAGE",
                "LIGHTRAG_VECTOR_STORAGE",
                "LIGHTRAG_DOC_STATUS_STORAGE",
                "LIGHTRAG_GRAPH_STORAGE",
            )
        ]
        for name in declared:
            backend = self.storage_backends.get(name, {})
            if not isinstance(backend, dict):
                continue
            required_keys = [str(item) for item in as_list(backend.get("required_keys", []))]
            selector_tokens = [str(item) for item in as_list(backend.get("selector_contains", []))]
            selected = any(
                token and token.lower() in value.lower()
                for token in selector_tokens
                for value in selector_values
            )
            configured = any(key in env and str(env.get(key, "")).strip() for key in required_keys)
            if not selected and not configured:
                self.add("storage", name, STATUS_SKIP, "Not selected/configured")
                continue
            missing = [
                key
                for key in required_keys
                if key not in env or is_placeholder(env.get(key), self.placeholders)
            ]
            self.add(
                "storage",
                name,
                STATUS_OK if not missing else STATUS_FAIL,
                "Required storage keys are present" if not missing else f"Missing/placeholder keys: {', '.join(missing)}",
                required=selected,
            )

    def check_provider_tools(self, env: dict[str, str]) -> None:
        bindings = {
            str(env.get("LLM_BINDING", "")).lower(),
            str(env.get("EMBEDDING_BINDING", "")).lower(),
        }
        if "ollama" in bindings or any(key.startswith("OLLAMA_") for key in env):
            command = [str(item) for item in as_list(self.commands.get("ollama", ["ollama", "list"]))]
            ok, output, _ = run_command(command, self.timeout)
            self.add(
                "provider",
                "ollama_cli",
                STATUS_OK if ok else STATUS_WARN,
                output if output else "ollama CLI is available",
                remediation="Install Ollama and pull the configured embedding/LLM models.",
            )

    def check_smoke_manifest(self) -> None:
        smoke = self.config.get("smoke_tests", {})
        if not smoke:
            return
        enabled = [name for name, value in smoke.items() if bool(value)]
        disabled = [name for name, value in smoke.items() if not bool(value)]
        self.add(
            "smoke",
            "manifest",
            STATUS_OK,
            f"enabled={', '.join(enabled) if enabled else 'none'}; disabled={len(disabled)}",
        )
        if smoke.get("import_package_exports", False):
            symbols = sorted(self.configured_export_symbols())
            import_lines = [
                "import importlib",
                "module = importlib.import_module('raganything')",
                f"symbols = {symbols!r}",
                "missing = [name for name in symbols if not hasattr(module, name)]",
                "assert not missing, missing",
            ]
            ok, output = python_import_check(
                self.python,
                "\n".join(import_lines),
                self.timeout,
                self.rag_dir,
            )
            self.add(
                "smoke",
                "import_package_exports",
                STATUS_OK if ok else STATUS_WARN,
                "Configured exports import successfully" if ok else output,
                remediation="Install RAG-Anything dependencies before enabling import smoke as a hard gate.",
            )

    def run(self) -> ToolReport:
        discovered = self.discover()
        self.check_project(discovered)
        self.check_discovery(discovered)
        self.check_coverage_manifest(discovered)
        env, env_report = self.check_env_files()
        self.check_env_values(env)
        self.check_provider_config(env)
        self.check_provider_tools(env)
        self.check_parsers(discovered, env)
        self.check_processors(discovered, env)
        self.check_format_features(discovered, env)
        self.check_storage_backends(env)
        self.check_cli_manifest(discovered)
        self.check_exports_and_api(discovered)
        self.check_smoke_manifest()
        return ToolReport(
            generated_at_epoch=time.time(),
            project_root=str(self.project_root),
            config_path=str(self.config_path),
            rag_dir=str(self.rag_dir),
            strict=self.strict,
            discovered=discovered,
            env=env_report,
            results=self.results,
        )


def report_to_dict(report: ToolReport) -> dict[str, Any]:
    data = asdict(report)
    data["counts"] = report.counts()
    return data


def print_report(report: ToolReport) -> None:
    counts = report.counts()
    print("RAG-Anything external tool check")
    print(f"Project: {report.project_root}")
    print(f"RAG dir: {report.rag_dir}")
    print(f"Config:  {report.config_path}")
    print(f"Counts:  OK={counts.get(STATUS_OK, 0)} WARN={counts.get(STATUS_WARN, 0)} FAIL={counts.get(STATUS_FAIL, 0)} SKIP={counts.get(STATUS_SKIP, 0)}")
    print()

    discovered = report.discovered
    parsers = discovered.get("parsers", {}).get("names", [])
    processors = sorted(discovered.get("processors", {}).keys())
    extras = sorted(discovered.get("pyproject", {}).get("optional_dependencies", {}).keys())
    env_keys = discovered.get("env_surface", {}).get("all_keys", [])
    cli = discovered.get("cli", {})
    exports = discovered.get("exports", {}).get("symbols", [])
    print("Offered by RAG-Anything:")
    print(f"  Parsers:     {', '.join(parsers) if parsers else 'none discovered'}")
    print(f"  Processors:  {', '.join(processors) if processors else 'none discovered'}")
    print(f"  Extras:      {', '.join(extras) if extras else 'none discovered'}")
    print(f"  Env keys:    {len(env_keys)} discovered")
    if cli:
        cli_summary = ", ".join(
            f"{name}:{len(info.get('arguments', []))}" for name, info in sorted(cli.items())
        )
        print(f"  CLI:         {cli_summary}")
    print(f"  Exports:     {len(exports)} discovered")
    print()

    current_category = ""
    for result in report.results:
        if result.category != current_category:
            current_category = result.category
            print(f"[{current_category}]")
        required = " required" if result.required else ""
        print(f"  {result.status:4} {result.name}{required}: {result.detail}")
        if result.remediation and result.status in {STATUS_WARN, STATUS_FAIL}:
            print(f"       fix: {result.remediation}")
    print()

    if report.has_failures():
        print("Result: FAIL")
    elif report.strict and report.has_warnings():
        print("Result: FAIL (strict warnings)")
    elif report.has_warnings():
        print("Result: WARN")
    else:
        print("Result: OK")


def write_report(path: Path, report: ToolReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report_to_dict(report), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def find_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


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
        print(f"rag_tool_check error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
