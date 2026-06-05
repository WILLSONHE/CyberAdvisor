"""Wiki 路径与指令解析共用。"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from bilibili.env import ROOT

WIKI = os.path.join(ROOT, "Wiki")
RAW = os.path.join(ROOT, "Raw")
TRACK_DIR = os.path.join(WIKI, "博主", "标的追踪")
TRACK_INACTIVE_DIR = os.path.join(TRACK_DIR, "不活跃标的")
OVERVIEW_MD = os.path.join(WIKI, "博主", "标的总览.md")

sys.path.insert(0, os.path.join(ROOT, "scripts"))
from raw_paths import RAW_PENDING_VIDEO, RAW_APPROVED_VIDEO  # noqa: E402

PENDING_VIDEO = RAW_PENDING_VIDEO
APPROVED_VIDEO = RAW_APPROVED_VIDEO
POOL_MD = os.path.join(WIKI, "数据", "博主标的池日报.md")
LOG_MD = os.path.join(WIKI, "log.md")

WIKI_LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
FM_BLOCK = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
REVIEW_STATUS = re.compile(r"^review_status:\s*(\S+)", re.M)
DONE_REVIEW = frozenset({"approved", "ingested"})

def format_hint(cmd: str, arg: str = "问题") -> str:
    return f"请校对格式{cmd} {{{arg}}}，以精确搜索"


def parse_tail_arg(text: str, verbs: tuple[str, ...]) -> tuple[str | None, str | None] | None:
    """解析「动词 + 参数」；返回 None 表示非该组动词。"""
    stripped = text.strip()
    if not stripped:
        return None
    parts = stripped.split(None, 1)
    verb = parts[0]
    if verb.lower() not in {v.lower() for v in verbs}:
        return None
    if len(parts) < 2 or not parts[1].strip():
        return None, format_hint(verb, _arg_label(verb))
    return parts[1].strip(), None


def _arg_label(verb: str) -> str:
    vl = verb.lower()
    if vl in ("trk", "追踪", "track"):
        return "标的"
    if vl in ("qry", "问", "query"):
        return "问题"
    return "参数"


def iter_wiki_md(*, include_pending_video: bool = True) -> list[Path]:
    root = Path(WIKI)
    paths: list[Path] = []
    for p in root.rglob("*.md"):
        paths.append(p)
    return paths


def build_wiki_index() -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    for p in iter_wiki_md():
        index.setdefault(p.stem, []).append(p)
    return index


def resolve_wiki_link(target: str, index: dict[str, list[Path]]) -> bool:
    key = target.strip()
    if not key or key.startswith("http"):
        return True
    if key in index:
        return True
    # Obsidian 别名：文件名含目标
    for stem in index:
        if stem == key or key in stem:
            return True
    return False


def read_text(path: os.PathLike | str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def pending_video_files() -> list[str]:
    if not os.path.isdir(PENDING_VIDEO):
        return []
    out: list[str] = []
    for name in sorted(os.listdir(PENDING_VIDEO)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(PENDING_VIDEO, name)
        text = read_text(path)
        m = FM_BLOCK.match(text)
        if m and REVIEW_STATUS.search(m.group(1)):
            status = REVIEW_STATUS.search(m.group(1)).group(1)
            if status in DONE_REVIEW:
                continue
        out.append(path)
    return out
