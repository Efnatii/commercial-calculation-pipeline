from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

CommandMain = Callable[[list[str] | None], int]


@dataclass(frozen=True)
class ModuleCommand:
    name: str
    title: str
    main: CommandMain


@dataclass(frozen=True)
class WrapperModule:
    id: str
    title: str
    description: str
    commands: tuple[ModuleCommand, ...]

    def get_command(self, name: str) -> ModuleCommand | None:
        for command in self.commands:
            if command.name == name:
                return command
        return None


__all__ = ["CommandMain", "ModuleCommand", "WrapperModule"]
