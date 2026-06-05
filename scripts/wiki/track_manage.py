"""标的追踪维护：活跃池归档、提及≥3 自动建页/回迁。"""
from __future__ import annotations

import os
import re
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from bilibili.env import ROOT
from wiki.common import (
    FM_BLOCK,
    RAW,
    TRACK_DIR,
    WIKI,
    iter_wiki_md,
    read_text,
)

INACTIVE_DIR = os.path.join(TRACK_DIR, "不活跃标的")
MIN_MENTIONS_FOR_TRACK = 3
SKIP_STEMS = frozenset({"股性-网宿科技"})

DATE_ISO = re.compile(r"(\d{4}-\d{2}-\d{2})")
DATE_SHORT = re.compile(r"(?<!\d)(\d{2})-(\d{2})-(\d{2})(?!\d)")


@dataclass
class MentionHit:
    date: str
    page: str
    context: str
    source: str


def active_pool_names() -> set[str]:
    try:
        from fine_screen import BLOGGER_STOCKS

        return set(BLOGGER_STOCKS.keys())
    except Exception:
        return set()


def find_track_path(name: str) -> str | None:
    for base in (TRACK_DIR, INACTIVE_DIR):
        path = os.path.join(base, f"{name}.md")
        if os.path.isfile(path):
            return path
    return None


def list_track_page_names(*, include_inactive: bool = True) -> list[str]:
    names: list[str] = []
    if os.path.isdir(TRACK_DIR):
        for f in os.listdir(TRACK_DIR):
            if f.endswith(".md") and os.path.isfile(os.path.join(TRACK_DIR, f)):
                names.append(f[:-3])
    if include_inactive and os.path.isdir(INACTIVE_DIR):
        for f in os.listdir(INACTIVE_DIR):
            if f.endswith(".md"):
                names.append(f[:-3])
    return sorted(set(names))


def _date_from_path(path: Path) -> str | None:
    m = DATE_ISO.search(path.stem)
    if m:
        return m.group(1)
    m = DATE_SHORT.search(path.stem)
    if m:
        y, mo, d = m.groups()
        return f"20{y}-{mo}-{d}"
    try:
        text = read_text(path)
    except OSError:
        return None
    fm = FM_BLOCK.match(text)
    if fm:
        dm = re.search(r"^date:\s*(\S+)", fm.group(1), re.M)
        if dm:
            return dm.group(1).strip()[:10]
    return None


def _wiki_page_label(path: Path) -> str:
    rel = path.relative_to(Path(WIKI))
    if rel.parts[:2] == ("每日复盘", path.name):
        return path.stem
    return path.stem


def _context_line(text: str, name: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if name in line and len(s) > 4 and not s.startswith("#"):
            return s[:200]
    for line in text.splitlines():
        if name in line:
            return line.strip()[:200]
    return ""


def collect_mentions(name: str) -> list[MentionHit]:
    """从 Raw + Wiki 收集含标的名的条目（每文件至多 1 条）。"""
    hits: list[MentionHit] = []
    seen_pages: set[str] = set()

    raw_dirs = [
        os.path.join(RAW, "已分析归档"),
        os.path.join(RAW, "未分析归档"),
        os.path.join(RAW, "已审阅视频文稿"),
    ]
    for base in raw_dirs:
        if not os.path.isdir(base):
            continue
        for fname in sorted(os.listdir(base)):
            if not fname.endswith(".md"):
                continue
            path = Path(os.path.join(base, fname))
            try:
                text = read_text(path)
            except OSError:
                continue
            if name not in text:
                continue
            page = path.stem
            if page in seen_pages:
                continue
            seen_pages.add(page)
            dt = _date_from_path(path) or "未知"
            ctx = _context_line(text, name)
            hits.append(
                MentionHit(
                    date=dt,
                    page=page,
                    context=ctx,
                    source=str(path.relative_to(ROOT)),
                )
            )

    for p in iter_wiki_md():
        if p.parent.name == "标的追踪":
            continue
        try:
            text = read_text(p)
        except OSError:
            continue
        if name not in text:
            continue
        page = _wiki_page_label(p)
        if page in seen_pages:
            continue
        seen_pages.add(page)
        dt = _date_from_path(p) or "未知"
        ctx = _context_line(text, name)
        rel = p.relative_to(Path(WIKI))
        hits.append(
            MentionHit(
                date=dt,
                page=page,
                context=ctx,
                source=f"Wiki/{rel.as_posix()}",
            )
        )

    def sort_key(h: MentionHit) -> tuple:
        if h.date == "未知":
            return ("9999", h.page)
        return (h.date, h.page)

    hits.sort(key=sort_key)
    return hits


def mention_count(name: str) -> int:
    return len(collect_mentions(name))


def _month_counts(hits: list[MentionHit]) -> list[tuple[str, int]]:
    c: Counter[str] = Counter()
    for h in hits:
        if h.date != "未知" and len(h.date) >= 7:
            c[h.date[:7]] += 1
    return sorted(c.items())


def render_track_page(name: str, hits: list[MentionHit]) -> str:
    n = len(hits)
    dates = [h.date for h in hits if h.date != "未知"]
    span = ""
    if dates:
        span = f"，跨越 {dates[0]} ~ {dates[-1]}"
    lines = [
        f"# {name} 全痕迹追踪",
        "",
        f"> 博主共提及 **{n}** 次{span}",
        "",
        "## 时间线",
        "",
        "| 日期 | 页面 | 上下文 |",
        "|------|------|--------|",
    ]
    for h in hits:
        ctx = h.context.replace("|", "｜") or "—"
        lines.append(f"| {h.date} | [[{h.page}]] | {ctx} |")
    lines.extend(["", "## 提及分布", ""])
    if dates:
        lines.append(f"- 首次提及：{dates[0]} [[{hits[0].page}]]")
        lines.append(f"- 最后提及：{dates[-1]} [[{hits[-1].page}]]")
    else:
        lines.append("- 首次提及：—")
        lines.append("- 最后提及：—")
    lines.extend(["", "| 月份 | 提及次数 |", "|------|--------|"])
    for month, cnt in _month_counts(hits):
        lines.append(f"| {month} | {cnt} |")
    lines.extend(
        [
            "",
            "## 相关链接",
            "",
            "- [[标的总览]]",
            "- [[选股框架]]",
            "",
        ]
    )
    return "\n".join(lines)


def _is_special_track_file(fname: str) -> bool:
    stem = fname[:-3] if fname.endswith(".md") else fname
    return stem in SKIP_STEMS or stem.startswith("股性-")


def _ensure_dirs() -> None:
    os.makedirs(TRACK_DIR, exist_ok=True)
    os.makedirs(INACTIVE_DIR, exist_ok=True)


def run_track_maintenance(*, refresh_existing: bool = False) -> str:
    """
    1. 非博主标的池 → 移入 不活跃标的/
    2. 标的池内且提及≥3 → 活跃目录建页/回迁；从 inactive 迁回 active
    """
    _ensure_dirs()
    pool = active_pool_names()
    if not pool:
        return "无法加载 BLOGGER_STOCKS，跳过标的追踪维护"

    moved_inactive: list[str] = []
    promoted: list[str] = []
    created: list[str] = []
    refreshed: list[str] = []

    # 1) 活跃目录下、不在标的池的追踪页 → 不活跃
    if os.path.isdir(TRACK_DIR):
        for fname in list(os.listdir(TRACK_DIR)):
            if not fname.endswith(".md") or _is_special_track_file(fname):
                continue
            name = fname[:-3]
            if name in pool:
                continue
            src = os.path.join(TRACK_DIR, fname)
            dst = os.path.join(INACTIVE_DIR, fname)
            if os.path.isfile(dst):
                os.remove(dst)
            shutil.move(src, dst)
            moved_inactive.append(name)

    # 2) 标的池：提及≥3 → 活跃目录
    for name in sorted(pool):
        hits = collect_mentions(name)
        cnt = len(hits)
        path_active = os.path.join(TRACK_DIR, f"{name}.md")
        path_inactive = os.path.join(INACTIVE_DIR, f"{name}.md")

        if cnt >= MIN_MENTIONS_FOR_TRACK:
            content = render_track_page(name, hits)
            if os.path.isfile(path_inactive):
                if os.path.isfile(path_active):
                    os.remove(path_active)
                shutil.move(path_inactive, path_active)
                promoted.append(name)
            elif not os.path.isfile(path_active):
                with open(path_active, "w", encoding="utf-8") as f:
                    f.write(content)
                created.append(name)
            elif refresh_existing:
                with open(path_active, "w", encoding="utf-8") as f:
                    f.write(content)
                refreshed.append(name)

    parts = [
        "# 标的追踪维护",
        "",
        f"> {datetime.now():%Y-%m-%d %H:%M} | 活跃池 {len(pool)} 只 | 建页阈值 ≥{MIN_MENTIONS_FOR_TRACK} 次提及",
        "",
    ]
    if moved_inactive:
        parts.append("## 移入 不活跃标的/")
        for n in moved_inactive:
            parts.append(f"- {n}")
        parts.append("")
    if promoted:
        parts.append("## 回迁活跃目录（原在不活跃标的/）")
        for n in promoted:
            parts.append(f"- {n}（{mention_count(n)} 次提及）")
        parts.append("")
    if created:
        parts.append("## 新建追踪页（活跃目录）")
        for n in created:
            parts.append(f"- {n}（{mention_count(n)} 次提及）")
        parts.append("")
    if refreshed:
        parts.append("## 刷新追踪页")
        for n in refreshed:
            parts.append(f"- {n}")
        parts.append("")

    active_n = len(
        [f for f in os.listdir(TRACK_DIR) if f.endswith(".md") and not _is_special_track_file(f)]
    ) if os.path.isdir(TRACK_DIR) else 0
    inactive_n = len(os.listdir(INACTIVE_DIR)) if os.path.isdir(INACTIVE_DIR) else 0
    parts.append(f"当前：活跃目录 **{active_n}** 页，不活跃标的/ **{inactive_n}** 页")

    if not (moved_inactive or promoted or created or refreshed):
        parts.append("\n（无变更）")

    return "\n".join(parts)
