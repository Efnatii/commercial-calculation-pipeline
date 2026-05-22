from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VisualItem:
    name: str
    status: str
    detail: str
    reason: str = ""
    note: str = ""


__all__ = ["VisualItem"]
