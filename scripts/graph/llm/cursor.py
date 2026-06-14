"""Cursor Cloud Agent 后端。"""
from __future__ import annotations

from typing import Any

from graph.llm.base import estimate_call_usd


class CursorLLM:
    name = "cursor_cloud"

    def complete(self, *, role: str, prompt: str, max_chars: int = 12000) -> dict[str, Any]:
        from ai_sim.agent_client import AgentClientError, run_analysis_prompt

        header = (
            f"你是 CyberAdvisor Graph 管线中的 **{role}**。"
            "仅输出 Markdown 分析正文，不要改仓库、不要 git、不要执行命令。\n\n"
        )
        full = header + prompt
        if len(full) > max_chars:
            full = full[: max_chars - 80] + "\n\n…（prompt 截断）"

        try:
            resp = run_analysis_prompt(full)
        except AgentClientError as e:
            raise
        text = (resp.get("result") or "").strip()
        usage = resp.get("usage") or {}
        usd, tokens = estimate_call_usd(full, text, usage=usage)
        return {
            "text": text,
            "usage_usd": usd,
            "tokens": tokens or resp.get("token_total") or 0,
            "agent_id": resp.get("agent_id"),
            "stub": False,
        }
