"""飞书 Bot 指令返回结构。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CommandResult:
    text: str = ""
    file_path: str | None = None
    file_name: str | None = None
    file_type: str = "stream"

    @classmethod
    def from_text(cls, text: str) -> "CommandResult":
        return cls(text=text)
