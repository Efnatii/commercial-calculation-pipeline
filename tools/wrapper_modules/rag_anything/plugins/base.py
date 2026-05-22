from __future__ import annotations

import argparse
from typing import Any, Protocol

from wrapper_modules.rag_anything.core.models import CheckResult


class CheckPlugin(Protocol):
    id: str
    title: str

    def discover(self, context: Any) -> dict[str, Any]: ...

    def check(self, context: Any, discovered: dict[str, Any]) -> list[CheckResult]: ...


class ConsolePanelPlugin(Protocol):
    id: str
    title: str

    def render(self, report: Any, context: Any) -> list[str]: ...


class CommandPlugin(Protocol):
    name: str

    def add_arguments(self, parser: argparse.ArgumentParser) -> None: ...

    def run(self, args: argparse.Namespace) -> int: ...


__all__ = ["CheckPlugin", "ConsolePanelPlugin", "CommandPlugin"]
