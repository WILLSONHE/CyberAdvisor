#!/usr/bin/env python3
"""
批量修复 Wiki 断链 [[...]]（chk 体检后运行）。

用法:
  python scripts/wiki/fix_links.py --dry-run
  python scripts/wiki/fix_links.py
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from bilibili.env import ROOT as ENV_ROOT  # noqa: E402
from wiki.common import (  # noqa: E402
    WIKI,
    WIKI_LINK,
    build_wiki_index,
    iter_wiki_md,
    read_text,
    resolve_wiki_link,
)

assert ENV_ROOT == ROOT

# 视频 / 日更 已知短名 → 实际页面 stem
MANUAL_ALIASES: dict[str, str] = {
    "其他材料/_index": "_index",
    "标的追踪/中际旭创": "中际旭创",
    "标的追踪/寒武纪": "寒武纪",
    "视频26-06-05-单根K线②": "视频26-06-06-单根K线②",
    "视频26-05-22-2028AI资本狂潮终局": "视频26-05-23-2028AI资本狂潮终局",
    "视频26-05-22-中国金融大棋秋后问斩": "视频26-05-24-中国金融大棋秋后问斩",
    "视频26-05-22-山雨欲来风满楼": "视频26-05-24-山雨欲来风满楼",
    "视频26-05-15-中国再通胀与全球重定价": "视频26-05-17-中国再通胀与全球重定价",
    "视频26-03-06 长鑫存储": "视频26-03-06-2026年十倍主线长鑫存储上市与国产半导体设备替代",
    "视频25-12-31-锂矿行业调研心得": "视频26-01-03-锂矿行业调研心得",
    "视频26-01-09-1月11日周末分享": "视频26-01-11-1月11日周末分享",
    "视频26-02-06-周末消息面随感": "视频26-02-08-周末消息面随感",
    "视频26-05-06 CPO深度研究": "视频26-05-06-光模块行业深度研究CPO技术革命与产业链格局重塑",
    "视频：充电咨询该怎么用": "视频26-05-26-充电资讯搭建信息差",
    "周复盘：26-04-30": "2026-04-30",
    "2026-04-05": "2026-04-03_4",
    "每日复盘": "index",
    "视频26-03-06 长鑫存储": "视频26-03-06-长鑫存储",
    "视频：26-05-06：光模块行业深度研究：CPO技术革命与产业链格局重塑": "光",
    "视频：26-03-06：2026年十倍主线：长鑫存储上市与国产半导体设备替代": "视频26-03-06-长鑫存储",
    "视频26-06-05-美股暴跌泡沫": "视频26-06-07-美股暴跌泡沫",
    "视频26-05-29-盈利铺就崎岖之路": "视频26-05-31-盈利铺就崎岖之路",
    "视频26-05-29-分化时代房地产消费港股": "视频26-05-30-分化时代房地产消费港股",
    "第四课有效市场假说": "市场认知框架",
    "复盘：25-05-21": "2025-05-21",
    "早盘：25-05-22": "2025-05-22",
}

_RAW_PREFIX = re.compile(
    r"^(复盘|早盘|午盘|动态|专栏|周复盘|研报|晚间复盘|周末补充)[：:]"
)
_RAW_DATE = re.compile(r"(\d{2})-(\d{2})-(\d{2})")
_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:-\S+)?$")
_VIDEO_COLON = re.compile(r"^视频[：:]")
_VIDEO_STEM = re.compile(r"^视频\d{2}-")
_BVID_RAW = re.compile(r"^(\d{2}-\d{2}-\d{2})_(BV[\w]+)_(.+)$", re.I)


def _load_daily_renames() -> dict[str, str]:
    """从最近一次含日更 rename 的 commit 提取 old→new stem。"""
    try:
        out = subprocess.check_output(
            ["git", "log", "-5", "--name-status", "--format=%H"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {}
    renames: dict[str, str] = {}
    current_commit = ""
    for line in out.splitlines():
        if re.fullmatch(r"[0-9a-f]{40}", line):
            current_commit = line
            continue
        if not line.startswith("R"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        old, new = parts[1].strip('"'), parts[2].strip('"')
        if not old.endswith(".md"):
            continue
        o_stem = Path(old).stem
        n_stem = Path(new).stem
        if o_stem != n_stem:
            renames[o_stem] = n_stem
    return renames


def _date_from_raw(target: str) -> str | None:
    m = _RAW_DATE.search(target)
    if not m:
        return None
    return f"20{m.group(1)}-{m.group(2)}-{m.group(3)}"


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _pick_video_by_date(date_yy: str, hint: str, video_stems: list[str]) -> str | None:
    """date_yy = 26-01-21；hint 为标题片段。"""
    prefix = f"视频{date_yy}"
    cands = [s for s in video_stems if s.startswith(prefix)]
    if not cands:
        # 允许 ±1 日发布（周复盘等）
        parts = date_yy.split("-")
        if len(parts) == 3:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            for delta in (1, -1, 2, -2):
                nd = d + delta
                if 1 <= nd <= 31:
                    alt = f"视频{parts[0]}-{parts[1]:02d}-{nd:02d}"
                    cands.extend(s for s in video_stems if s.startswith(alt))
        cands = sorted(set(cands))
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0]
    hint_norm = re.sub(r"\s+", "", hint)
    best, score = None, 0.0
    for c in cands:
        tail = c.split("-", 3)[-1] if c.count("-") >= 3 else c
        s = _similarity(hint_norm, re.sub(r"\s+", "", tail))
        if s > score:
            score, best = s, c
    return best if score >= 0.25 else cands[0]


def _resolve_bvid_raw(target: str, video_stems: list[str]) -> str | None:
    m = _BVID_RAW.match(target)
    if not m:
        return None
    date_part, bvid, title = m.group(1), m.group(2).upper(), m.group(3)
    for stem in video_stems:
        if bvid in stem.upper() or title in stem:
            return stem
    return _pick_video_by_date(date_part, title, video_stems)


def resolve_target(
    target: str,
    index: dict[str, list[Path]],
    daily_renames: dict[str, str],
    video_stems: list[str],
) -> str | None:
    key = target.strip()
    if not key or key.startswith("http"):
        return None
    if key in ("标的总览", "index", "log", "YYYY-MM-DD"):
        return None
    if resolve_wiki_link(key, index):
        return None  # already valid

    if key in MANUAL_ALIASES:
        rep = MANUAL_ALIASES[key]
        if rep in index or resolve_wiki_link(rep, index):
            return rep

    if key in daily_renames:
        rep = daily_renames[key]
        if rep in index:
            return rep

    if key.endswith("-日更"):
        base = key[:-3]
        if base in index:
            return base

    if _RAW_PREFIX.match(key):
        iso = _date_from_raw(key)
        if iso:
            if iso in index:
                return iso
            if iso in daily_renames and daily_renames[iso] in index:
                return daily_renames[iso]
            # 带后缀日更 2026-01-15-日更
            for stem in index:
                if stem.startswith(iso):
                    return stem

    if _ISO_DATE.match(key):
        if key in daily_renames:
            rep = daily_renames[key]
            if rep in index:
                return rep
        # 旧 ISO 日期不存在 → rename 表
        for stem in index:
            if stem.startswith(key):
                return stem

    if _VIDEO_COLON.match(key):
        m = _RAW_DATE.search(key)
        if m:
            yy = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            hint = key.split("：", 1)[-1] if "：" in key else key.split(":", 1)[-1]
            picked = _pick_video_by_date(yy, hint, video_stems)
            if picked:
                return picked

    if _VIDEO_STEM.match(key):
        if key in MANUAL_ALIASES:
            return MANUAL_ALIASES[key]
        # 模糊：stem 包含关系
        for stem in video_stems:
            if key in stem or stem.startswith(key.split()[0]):
                tail_key = key.replace("视频", "")
                tail_stem = stem.replace("视频", "")
                if _similarity(tail_key, tail_stem) >= 0.55:
                    return stem
        # 去掉空格再比
        kn = re.sub(r"\s+", "", key)
        for stem in video_stems:
            if kn in re.sub(r"\s+", "", stem):
                return stem

    if _BVID_RAW.match(key):
        rep = _resolve_bvid_raw(key, video_stems)
        if rep:
            return rep

    if key.startswith("标的追踪/"):
        sub = key.split("/", 1)[1]
        if sub in index:
            return sub

    return None


def apply_fixes(*, dry_run: bool) -> dict:
    index = build_wiki_index()
    daily_renames = _load_daily_renames()
    video_stems = sorted(s for s in index if s.startswith("视频"))
    stats = {"files": 0, "replacements": 0, "unresolved": 0}
    unresolved_targets: set[str] = set()

    for path in iter_wiki_md():
        text = read_text(path)
        changed = False

        def _sub(m: re.Match[str]) -> str:
            nonlocal changed, stats
            target = m.group(1).strip()
            suffix = m.group(0)[m.group(0).find(target) + len(target) :]
            full = m.group(0)
            if target in ("标的总览", "index", "log", "YYYY-MM-DD"):
                return full
            if resolve_wiki_link(target, index):
                return full
            rep = resolve_target(target, index, daily_renames, video_stems)
            if not rep:
                stats["unresolved"] += 1
                unresolved_targets.add(target)
                return full
            stats["replacements"] += 1
            changed = True
            return f"[[{rep}{suffix}"

        new_text = WIKI_LINK.sub(_sub, text)
        if changed:
            stats["files"] += 1
            if not dry_run:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_text if new_text.endswith("\n") else new_text + "\n")

    stats["unresolved_unique"] = len(unresolved_targets)
    if unresolved_targets:
        stats["unresolved_sample"] = sorted(unresolved_targets)[:20]
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="修复 Wiki 断链")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    stats = apply_fixes(dry_run=args.dry_run)
    tag = "DRY-RUN" if args.dry_run else "OK"
    print(f"[{tag}] {stats['files']} files, {stats['replacements']} replacements")
    print(f"  unresolved: {stats.get('unresolved_unique', 0)} unique targets")
    for t in stats.get("unresolved_sample", []):
        print(f"    - {t}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
