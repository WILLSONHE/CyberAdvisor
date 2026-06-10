"""trk {标的} — 标的全痕迹追踪。"""
from __future__ import annotations

import os
import re
from pathlib import Path

from bilibili.env import ROOT
from wiki.common import OVERVIEW_MD, RAW, TRACK_DIR, WIKI, iter_wiki_md, read_text
from wiki.track_manage import INACTIVE_DIR, collect_mentions, find_track_path, list_track_page_names


def _list_track_names() -> list[str]:
    return list_track_page_names(include_inactive=True)


def resolve_stock_name(query: str) -> str:
    q = query.strip()
    if not q:
        return q
    if find_track_path(q):
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


def _track_location_hint(path: str | None) -> str:
    if not path:
        return ""
    if path.startswith(INACTIVE_DIR):
        return "（不活跃标的/）"
    return ""


def _grep_mentions(name: str, limit: int = 12) -> str:
    hits: list[str] = []
    for h in collect_mentions(name)[:limit]:
        hits.append(f"- {h.source}: {h.context[:120] if h.context else '—'}")
    if not hits:
        return f"（Wiki/Raw 中未 grep 到「{name}」）"
    return "【补充提及（grep）】\n" + "\n".join(hits)


def track_stock(query: str) -> str:
    name = resolve_stock_name(query)
    parts: list[str] = [f"# trk {name}", ""]

    overview = _overview_snippet(name)
    if overview:
        parts.extend([overview, ""])

    track_path = find_track_path(name)
    if track_path:
        loc = _track_location_hint(track_path)
        rel = Path(track_path).relative_to(ROOT)
        parts.append(f"📁 `{rel.as_posix()}` {loc}".strip())
        parts.append("")
        parts.append(read_text(track_path))
    else:
        parts.append(f"（尚无专用追踪页 Wiki/内容源/标的追踪/{name}.md）")
        parts.extend(["", _grep_mentions(name)])

    return "\n".join(parts).strip()
