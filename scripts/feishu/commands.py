"""飞书 Bot 指令路由（本机轻量查询，完整 AI 仍走 Cursor）。"""
from __future__ import annotations

import glob
import os
import re

from bilibili.env import ROOT

MAX_CHUNK = 3500


def _read_tail(path: str, max_chars: int = 6000) -> str:
    if not os.path.isfile(path):
        return f"（文件不存在：{path}）"
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if len(text) <= max_chars:
        return text
    return "…（内容过长，仅显示末尾）\n\n" + text[-max_chars:]


def _latest_sug_path() -> str | None:
    files = sorted(glob.glob(os.path.join(ROOT, "SugVault", "*_sug.md")), reverse=True)
    return files[0] if files else None


def _extract_one_liner(md: str) -> str:
    m = re.search(r"## 今日一句话\s*\n+>\s*(.+)", md)
    return m.group(1).strip() if m else ""


def handle_command(text: str) -> str:
    cmd = text.strip()
    lower = cmd.lower()

    if lower in ("help", "帮助", "?", "？"):
        return (
            "CyberAdvisor 飞书 Bot（本机）\n\n"
            "可用指令：\n"
            "• sug — 最新交易策略报告\n"
            "• 持仓 / portfolio — 当前持仓\n"
            "• 日报 / pool — 博主标的池日报摘要\n"
            "• ping — 连通测试\n\n"
            "完整 ing / qry / 深度 sug 请在 Cursor 对话（需加载 finance-wiki skill）。"
        )

    if lower in ("ping", "测试", "test"):
        return "pong — CyberAdvisor Bot 在线"

    if lower in ("sug", "交易策略", "开仓"):
        path = _latest_sug_path()
        if not path:
            return "尚无 sug 报告。请先跑 daily.bat，再在 Cursor 说 sug（会写入 SugVault/）。"
        return _read_tail(path, MAX_CHUNK * 2)

    if lower in ("持仓", "portfolio"):
        return _read_tail(os.path.join(ROOT, "portfolio.md"), MAX_CHUNK)

    if lower in ("日报", "pool", "标的池"):
        return _read_tail(os.path.join(ROOT, "Wiki", "数据", "博主标的池日报.md"), MAX_CHUNK * 2)

    return (
        f"未识别指令：{cmd}\n"
        "发送「帮助」查看可用指令。"
    )


def split_reply(text: str, chunk_size: int = MAX_CHUNK) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    parts: list[str] = []
    start = 0
    while start < len(text):
        parts.append(text[start : start + chunk_size])
        start += chunk_size
    return parts
