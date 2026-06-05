"""trk {标的} — 博主标的全痕迹追踪。"""
from __future__ import annotations

import os
import re
from pathlib import Path

from bilibili.env import ROOT
from wiki.common import OVERVIEW_MD, RAW, TRACK_DIR, WIKI, iter_wiki_md, read_text


def _list_track_names() -> list[str]:
    if not os.path.isdir(TRACK_DIR):
        return []
    return sorted(f[:-3] for f in os.listdir(TRACK_DIR) if f.endswith(".md"))


def resolve_stock_name(query: str) -> str:
    q = query.strip()
    if not q:
        return q
    if os.path.isfile(os.path.join(TRACK_DIR, f"{q}.md")):
        return q
    for name in _list_track_names():
        if name.lower() == q.lower():
            return name
    for name in _list_track_names():
        if q in name or name in q:
            return name
    return q


def _overview_snippet(name: str) -> str:
    if not os.path.isfile(OVERVIEW_MD):
        return ""
    for line in read_text(OVERVIEW_MD).splitlines():
        if line.startswith("|") and re.search(rf"\|\s*{re.escape(name)}\s*\|", line):
            return "【标的总览】\n" + line
    return ""


def _grep_mentions(name: str, limit: int = 12) -> str:
    hits: list[str] = []
    raw_dirs = [
        os.path.join(RAW, "已分析归档"),
        os.path.join(RAW, "未分析归档"),
    ]
    for base in raw_dirs:
        if not os.path.isdir(base):
            continue
        for fname in sorted(os.listdir(base), reverse=True):
            if not fname.endswith(".md"):
                continue
            path = os.path.join(base, fname)
            try:
                text = read_text(path)
            except OSError:
                continue
            if name not in text:
                continue
            for line in text.splitlines():
                if name in line and len(line.strip()) > 4:
                    rel = Path(path).relative_to(ROOT)
                    hits.append(f"- {rel}: {line.strip()[:120]}")
                    break
            if len(hits) >= limit:
                break

    if len(hits) < limit:
        wiki_root = Path(WIKI)
        for p in sorted(iter_wiki_md(), key=lambda x: x.stat().st_mtime, reverse=True):
            if p.parent.name == "标的追踪" and p.stem == name:
                continue
            try:
                text = read_text(p)
            except OSError:
                continue
            if name not in text:
                continue
            for line in text.splitlines():
                if name in line and not line.strip().startswith("#"):
                    rel = p.relative_to(wiki_root)
                    hits.append(f"- Wiki/{rel}: {line.strip()[:120]}")
                    break
            if len(hits) >= limit:
                break

    if not hits:
        return f"（Wiki/Raw 中未 grep 到「{name}」）"
    return "【补充提及（grep）】\n" + "\n".join(hits[:limit])


def track_stock(query: str) -> str:
    name = resolve_stock_name(query)
    parts: list[str] = [f"# trk {name}", ""]

    overview = _overview_snippet(name)
    if overview:
        parts.extend([overview, ""])

    track_path = os.path.join(TRACK_DIR, f"{name}.md")
    if os.path.isfile(track_path):
        parts.append(read_text(track_path))
    else:
        parts.append(f"（尚无专用追踪页 Wiki/博主/标的追踪/{name}.md）")
        parts.extend(["", _grep_mentions(name)])

    return "\n".join(parts).strip()
