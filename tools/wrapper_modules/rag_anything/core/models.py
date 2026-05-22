from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

STATUS_OK = "OK"
STATUS_WARN = "WARN"
STATUS_FAIL = "FAIL"
STATUS_SKIP = "SKIP"


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


__all__ = [
    "STATUS_OK",
    "STATUS_WARN",
    "STATUS_FAIL",
    "STATUS_SKIP",
    "CheckResult",
    "ToolReport",
]
