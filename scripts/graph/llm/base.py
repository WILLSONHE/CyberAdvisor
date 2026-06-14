"""Graph 管线 LLM 后端抽象（非 LangGraph）。"""
from __future__ import annotations

from typing import Any, Protocol


class LLMBackend(Protocol):
    name: str

    def complete(self, *, role: str, prompt: str, max_chars: int = 12000) -> dict[str, Any]:
        """返回 {text, usage_usd, tokens}。"""


def estimate_call_usd(prompt: str, result: str, *, usage: dict[str, Any] | None = None) -> tuple[float, int]:
    if usage and not usage.get("estimated"):
        total = sum(int(usage.get(k) or 0) for k in ("inputTokens", "outputTokens", "cacheReadTokens", "cacheWriteTokens"))
        if total:
            # Cursor/Composer 粗估：$2/M blended
            return round(total * 2.0 / 1_000_000, 4), total
    chars = len(prompt) + len(result or "")
    tokens = max(500, chars // 4)
    return round(tokens * 2.0 / 1_000_000, 4), tokens
