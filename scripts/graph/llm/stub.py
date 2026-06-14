"""Stub LLM（dry-run / 冒烟测试）。"""
from __future__ import annotations

from typing import Any

from graph.llm.base import estimate_call_usd


class StubLLM:
    name = "stub"

    def complete(self, *, role: str, prompt: str, max_chars: int = 12000) -> dict[str, Any]:
        text = (
            f"<!-- stub role={role} -->\n"
            f"**[{role}]** 占位输出（dry-run）。\n\n"
            f"- 输入约 {len(prompt)} 字符\n"
            f"- 请设置 `GRAPH_PIPELINE_ENABLED=1` 且提供 `CURSOR_API_KEY` 以启用 Cloud Agent。\n"
        )
        usd, tokens = estimate_call_usd(prompt, text)
        return {"text": text, "usage_usd": usd, "tokens": tokens, "stub": True}
