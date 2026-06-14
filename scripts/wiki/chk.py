"""chk — Wiki 结构体检（只读，不改文件）。"""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

from bilibili.env import ROOT
from raw_paths import list_pending_files, list_pending_material_files
from wiki.common import (
    LOG_MD,
    POOL_MD,
    TRACK_DIR,
    TRACK_INACTIVE_DIR,
    WIKI,
    WIKI_LINK,
    build_wiki_index,
    iter_wiki_md,
    pending_video_files,
    read_text,
    resolve_wiki_link,
)

OVERVIEW_MD = os.path.join(WIKI, "内容源", "标的总览.md")
STATUS_EMOJI = re.compile(r"[🟢🟡🔴⚫]")


def _count_wiki_pages() -> int:
    return len(iter_wiki_md())


def _check_broken_links(max_show: int = 8) -> tuple[int, list[str]]:
    index = build_wiki_index()
    broken: list[str] = []
    for p in iter_wiki_md():
        try:
            text = read_text(p)
        except OSError:
            continue
        for m in WIKI_LINK.finditer(text):
            target = m.group(1).strip()
            if target in ("标的总览", "index", "log", "YYYY-MM-DD", "每日复盘"):
                continue
            if not resolve_wiki_link(target, index):
                rel = p.relative_to(Path(WIKI))
                broken.append(f"{rel} → [[{target}]]")
    broken = sorted(set(broken))
    return len(broken), broken[:max_show]


def _stale_active_overview() -> list[str]:
    """活跃区表格行中，标的名含 🟡/🔴/⚫ 或明显非 🟢 的摘要。"""
    if not os.path.isfile(OVERVIEW_MD):
        return []
    text = read_text(OVERVIEW_MD)
    in_active = False
    stale: list[str] = []
    for line in text.splitlines():
        if "## 🟢 近期活跃推荐" in line:
            in_active = True
            continue
        if in_active and line.startswith("## ") and "近期活跃" not in line:
            break
        if in_active and line.startswith("|") and "| 标的 |" not in line and "---" not in line:
            if STATUS_EMOJI.search(line) and "🟢" not in line:
                stale.append(line.strip())
    return stale[:6]


def _last_log_line() -> str:
    if not os.path.isfile(LOG_MD):
        return "（无 log.md）"
    for line in read_text(LOG_MD).splitlines():
        if line.startswith("## ["):
            return line.strip()
    return "（log 无条目）"


def _pool_updated() -> str:
    if not os.path.isfile(POOL_MD):
        return "（无标的池日报）"
    for line in read_text(POOL_MD).splitlines()[:8]:
        if "更新时间" in line or "生成" in line or re.match(r"^>\s*\d{4}", line):
            return line.strip()
    return f"（mtime {datetime.fromtimestamp(os.path.getmtime(POOL_MD)):%Y-%m-%d %H:%M}）"


def run_chk() -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    raw_pending = list_pending_files()
    material_pending = list_pending_material_files()
    video_pending = pending_video_files()
    track_count = 0
    inactive_count = 0
    if os.path.isdir(TRACK_DIR):
        track_count = len(
            [
                f
                for f in os.listdir(TRACK_DIR)
                if f.endswith(".md") and os.path.isfile(os.path.join(TRACK_DIR, f))
            ]
        )
    if os.path.isdir(TRACK_INACTIVE_DIR):
        inactive_count = len([f for f in os.listdir(TRACK_INACTIVE_DIR) if f.endswith(".md")])
    broken_n, broken_sample = _check_broken_links()
    stale = _stale_active_overview()

    lines = [
        f"# Wiki 体检报告",
        f"",
        f"> 只读检查，{now}。深度修复请在 Cursor 说 `chk`（AI）。",
        f"",
        f"## 待处理",
        f"",
        f"- Raw 待 ing：{len(raw_pending)} 篇",
    ]
    for p in raw_pending[:5]:
        lines.append(f"  - {Path(p).relative_to(ROOT)}")
    if len(raw_pending) > 5:
        lines.append(f"  - …共 {len(raw_pending)} 篇")

    lines.append(f"- 其他材料待 ing：{len(material_pending)} 个")
    for p in material_pending[:5]:
        lines.append(f"  - {Path(p).relative_to(ROOT)}")
    if len(material_pending) > 5:
        lines.append(f"  - …共 {len(material_pending)} 个")

    lines.append(f"- 视频稿待审/未 ing：{len(video_pending)} 篇")
    for p in video_pending[:5]:
        lines.append(f"  - {Path(p).relative_to(ROOT)}")

    lines.extend(
        [
            "",
            "## 结构",
            "",
            f"- Wiki 页面数：{_count_wiki_pages()}",
            f"- 标的追踪专页：{track_count}（活跃目录）+ {inactive_count}（不活跃标的/）",
            f"- 断链 [[...]]：{broken_n} 处",
        ]
    )
    for item in broken_sample:
        lines.append(f"  - {item}")
    if broken_n > len(broken_sample):
        lines.append(f"  - …另有 {broken_n - len(broken_sample)} 处")

    lines.extend(["", "## 时效性（标的总览活跃区）", ""])
    if stale:
        lines.append("- 活跃区内非 🟢 状态行（建议 Cursor chk 复核）：")
        for row in stale:
            lines.append(f"  - {row[:100]}")
    else:
        lines.append("- 活跃区抽样：未发现明显 🟡/🔴/⚫ 行")

    lines.extend(
        [
            "",
            "## 数据新鲜度",
            "",
            f"- 标的池日报：{_pool_updated()}",
            f"- 最近 log：{_last_log_line()}",
        ]
    )
    return "\n".join(lines)
