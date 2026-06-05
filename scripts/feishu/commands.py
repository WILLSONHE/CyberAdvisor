"""飞书 Bot 指令路由（本机轻量查询，完整 AI 仍走 Cursor）。"""
from __future__ import annotations

import os
import re

from bilibili.env import ROOT
from portfolio_utils import (
    filter_pool_md,
    filter_portfolio_md,
    format_hint,
    latest_sug_path,
    parse_holder_arg,
)
from wiki import run_chk, search_wiki, track_stock
from wiki.common import format_hint as wiki_format_hint
from wiki.common import parse_tail_arg

MAX_CHUNK = 3500

SUG_VERBS = ("sug", "交易策略", "开仓")
HOLDING_VERBS = ("持仓", "portfolio")
POOL_VERBS = ("日报", "pool", "标的池")
TRK_VERBS = ("trk", "追踪", "track")
CHK_VERBS = ("chk", "体检", "check")
QRY_VERBS = ("qry", "问", "query")


def _read_tail(path: str, max_chars: int = 6000) -> str:
    if not os.path.isfile(path):
        return f"（文件不存在：{path}）"
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return _truncate(text, max_chars)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return "…（内容过长，仅显示末尾）\n\n" + text[-max_chars:]


def _extract_one_liner(md: str) -> str:
    m = re.search(r"## 今日一句话\s*\n+>\s*(.+)", md)
    return m.group(1).strip() if m else ""


def _handle_holder_command(text: str, verbs: tuple[str, ...], handler) -> str | None:
    parsed = parse_holder_arg(text, verbs)
    if parsed is None:
        return None
    holder, err = parsed
    if err:
        return err
    assert holder is not None
    return handler(holder)


def _handle_tail_command(text: str, verbs: tuple[str, ...], handler, *, arg_label: str) -> str | None:
    parsed = parse_tail_arg(text, verbs)
    if parsed is None:
        return None
    arg, err = parsed
    if err:
        return err
    assert arg is not None
    return handler(arg)


def handle_command(text: str) -> str:
    cmd = text.strip()
    lower = cmd.lower()

    if lower in ("help", "帮助", "?", "？"):
        names_hint = ""
        try:
            from portfolio_utils import load_holder_names

            names = load_holder_names()
            if names:
                names_hint = f"\n当前持有人：{', '.join(names)}"
        except Exception:
            pass
        return (
            "CyberAdvisor 飞书 Bot（本机）\n\n"
            "【持仓 / 交易】（需持有人）\n"
            "• sug {持有人}\n"
            "• 持仓 {持有人}\n"
            "• 标的池 {持有人}\n\n"
            "【Wiki 查询】\n"
            "• trk {标的} — 博主痕迹追踪\n"
            "• chk — Wiki 体检\n"
            "• qry {问题} — Wiki 关键词检索\n\n"
            "• ping — 连通测试\n\n"
            f"示例：sug Wilson / trk 寒武纪 / qry 存储{names_hint}\n\n"
            "深度 ing / AI 版 qry·chk·sug 生成 → Cursor + finance-wiki skill。"
        )

    if lower in ("ping", "测试", "test"):
        return "pong — CyberAdvisor Bot 在线"

    if lower in CHK_VERBS:
        return _truncate(run_chk(), MAX_CHUNK * 2)

    reply = _handle_tail_command(
        cmd, TRK_VERBS, lambda name: _truncate(track_stock(name), MAX_CHUNK * 2), arg_label="标的"
    )
    if reply is not None:
        return reply

    reply = _handle_tail_command(
        cmd, QRY_VERBS, lambda q: _truncate(search_wiki(q), MAX_CHUNK * 2), arg_label="问题"
    )
    if reply is not None:
        return reply

    reply = _handle_holder_command(
        cmd,
        SUG_VERBS,
        lambda holder: _read_tail(latest_sug_path(holder) or "", MAX_CHUNK * 2)
        if latest_sug_path(holder)
        else (
            f"尚无 {holder} 的 sug 报告。请在 Cursor 说「sug {holder}」"
            f"（会写入 SugVault/YYYY-MM-DD_{holder}_sug.md）。"
        ),
    )
    if reply is not None:
        return reply

    reply = _handle_holder_command(
        cmd,
        HOLDING_VERBS,
        lambda holder: _truncate(filter_portfolio_md(holder), MAX_CHUNK),
    )
    if reply is not None:
        return reply

    reply = _handle_holder_command(
        cmd,
        POOL_VERBS,
        lambda holder: _truncate(filter_pool_md(holder), MAX_CHUNK * 2),
    )
    if reply is not None:
        return reply

    if lower in SUG_VERBS:
        return format_hint("sug")
    if lower in HOLDING_VERBS:
        return format_hint("持仓")
    if lower in POOL_VERBS:
        return format_hint("标的池")
    if lower in TRK_VERBS:
        return wiki_format_hint("trk", "标的")
    if lower in QRY_VERBS:
        return wiki_format_hint("qry", "问题")

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
