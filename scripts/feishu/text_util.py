"""飞书文本编码与 Agent 错误分条（Bot 内容类回复已改走 delivery.py 发 .md 附件）。"""
from __future__ import annotations

import os
import re
import sys

MAX_CHUNK = 3500

_UTF8_REPLACEMENT = b"\xef\xbf\xbd"


def configure_stdio_utf8() -> None:
    """Windows 下强制进程 stdio 使用 UTF-8（避免日志/子进程乱码）。"""
    if sys.platform != "win32":
        return
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _strip_damaged_tail(text: str) -> str:
    """去掉 §七 追加损坏时常见的半截 Markdown 标题。"""
    text = text.rstrip("\r\n")
    marker = "## 七、研判总结"
    idx = text.rfind(marker)
    if idx >= 0:
        tail = text[idx + len(marker) :]
        if not tail.strip() or tail.lstrip().startswith("##") or "\ufffd" in tail:
            text = text[: idx + len(marker)].rstrip()
    lines = text.split("\n")
    while lines and re.match(r"^##\s*$", lines[-1]):
        lines.pop()
    return "\n".join(lines).rstrip()


def decode_text_bytes(raw: bytes) -> tuple[str, bool]:
    """
    解码文本字节，返回 (文本, 是否因损坏截断)。
    SugVault 若经 PowerShell 重定向追加，§七 后常混入 UTF-8 替换字节 \\xef\\xbf\\xbd。
    """
    if not raw:
        return "", False

    if raw.startswith(b"\xff\xfe"):
        return raw.decode("utf-16-le"), False
    if raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16-be"), False

    pos = raw.find(_UTF8_REPLACEMENT)
    if pos >= 0:
        return _strip_damaged_tail(raw[:pos].decode("utf-8")), True

    try:
        return raw.decode("utf-8"), False
    except UnicodeDecodeError:
        pass

    for enc in ("utf-8-sig", "gb18030", "gbk"):
        try:
            return raw.decode(enc), False
        except UnicodeDecodeError:
            continue

    text = raw.decode("utf-8", errors="replace")
    if "\ufffd" in text:
        return _strip_damaged_tail(text[: text.index("\ufffd")]), True
    return text, False


def read_text_file(path: str, *, max_chars: int | None = None) -> tuple[str, bool]:
    """读本地文本；返回 (内容, 是否因编码损坏截断尾部)。"""
    if not os.path.isfile(path):
        return f"（文件不存在：{path}）", False
    raw = open(path, "rb").read()
    text, truncated = decode_text_bytes(raw)
    if max_chars and len(text) > max_chars:
        text = "…（内容过长，仅显示末尾）\n\n" + text[-max_chars:]
    return text, truncated


def encoding_damage_note(*, holder: str = "", session: str | None = None) -> str:
    sess = f" {session}" if session else ""
    who = f"{holder}{sess}" if holder else "对应持有人"
    return (
        f"⚠️ 报告尾部（§七 起）生成时编码损坏已省略。"
        f"请重新生成：`agent sug {who}`\n\n"
    )


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
