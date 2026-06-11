"""飞书 Bot 指令返回结构。"""
from __future__ import annotations

import os
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
    text_only: bool = False
    delete_file_after_send: bool = False
    md_filename: str = ""

    @classmethod
    def from_text(cls, text: str) -> "CommandResult":
        return cls(text=text, text_only=True)

    @classmethod
    def from_markdown(cls, body: str, *, filename: str) -> "CommandResult":
        return cls(text=body, md_filename=filename, delete_file_after_send=True)

    @classmethod
    def from_existing_file(cls, path: str, *, file_name: str | None = None) -> "CommandResult":
        return cls(
            file_path=path,
            file_name=file_name or os.path.basename(path),
            delete_file_after_send=False,
        )

    @classmethod
    def async_agent(cls, ack: str, tasks: list["AgentTaskSpec"]) -> "CommandResult":
        return cls(text=ack, agent_tasks=tasks, text_only=True)
