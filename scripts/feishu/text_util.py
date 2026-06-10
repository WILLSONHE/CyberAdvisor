"""飞书消息分条。"""
from __future__ import annotations

import re

MAX_CHUNK = 3500


def extract_one_liner(body: str) -> str:
    """从 sug 正文提取「今日一句话」段落首行。"""
    m = re.search(
        r"##\s*今日一句话\s*\n+([^\n#]+)",
        body,
        re.IGNORECASE,
    )
    return m.group(1).strip() if m else ""


def split_reply(text: str, chunk_size: int = MAX_CHUNK) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    parts: list[str] = []
    start = 0
    while start < len(text):
        parts.append(text[start : start + chunk_size])
        start += chunk_size
    return parts
