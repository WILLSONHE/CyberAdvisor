"""飞书 Bot 指令返回结构。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from feishu.agent_jobs import AgentTaskSpec


@dataclass
class CommandResult:
    text: str = ""
    file_path: str | None = None
    file_name: str | None = None
    file_type: str = "stream"
    agent_tasks: list = field(default_factory=list)

    @classmethod
    def from_text(cls, text: str) -> "CommandResult":
        return cls(text=text)

    @classmethod
    def async_agent(cls, ack: str, tasks: list["AgentTaskSpec"]) -> "CommandResult":
        return cls(text=ack, agent_tasks=tasks)
