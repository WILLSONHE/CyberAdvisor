#!/usr/bin/env python3
"""一次性迁移：旧 Wiki/Raw 待审阅视频文稿 → Raw/未审阅视频文稿/；已审批/已入库 → Raw/已审阅视频文稿/"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from raw_paths import (  # noqa: E402
    LEGACY_PENDING_VIDEO,
    RAW_APPROVED_VIDEO,
    RAW_PENDING_VIDEO,
    ensure_raw_dirs,
)

FM_SPLIT = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
META_REVIEW = re.compile(r"^review_status:\s*(\S+)", re.M)
MOVE_TO_APPROVED = frozenset({"approved", "ingested"})
STATE_PATH = os.path.join(ROOT, "Wiki", "数据", "bilibili_sync.json")


def _review_status(path: str) -> str:
    text = open(path, encoding="utf-8").read()
    m = FM_SPLIT.match(text)
    if not m:
        return ""
    rm = META_REVIEW.search(m.group(1))
    return rm.group(1).strip() if rm else ""


def migrate_dirs() -> tuple[int, int]:
    ensure_raw_dirs()
    if os.path.isdir(LEGACY_PENDING_VIDEO):
        for name in os.listdir(LEGACY_PENDING_VIDEO):
            src = os.path.join(LEGACY_PENDING_VIDEO, name)
            if not os.path.isfile(src):
                continue
            dest = os.path.join(RAW_PENDING_VIDEO, name)
            if os.path.exists(dest):
                base, ext = os.path.splitext(name)
                i = 2
                while os.path.exists(dest):
                    dest = os.path.join(RAW_PENDING_VIDEO, f"{base}_{i}{ext}")
                    i += 1
            shutil.move(src, dest)
            print(f"  move legacy → 未审阅: {name}")
        try:
            os.rmdir(LEGACY_PENDING_VIDEO)
        except OSError:
            pass

    moved = 0
    kept = 0
    for path in sorted(glob.glob(os.path.join(RAW_PENDING_VIDEO, "*.md"))):
        status = _review_status(path)
        if status in MOVE_TO_APPROVED:
            dest = os.path.join(RAW_APPROVED_VIDEO, os.path.basename(path))
            if os.path.exists(dest):
                base, ext = os.path.splitext(os.path.basename(path))
                i = 2
                while os.path.exists(dest):
                    dest = os.path.join(RAW_APPROVED_VIDEO, f"{base}_{i}{ext}")
                    i += 1
            shutil.move(path, dest)
            moved += 1
            print(f"  → 已审阅: {os.path.basename(dest)} ({status})")
        else:
            kept += 1
    return moved, kept


def fix_bilibili_sync() -> int:
    if not os.path.isfile(STATE_PATH):
        return 0
    data = json.load(open(STATE_PATH, encoding="utf-8"))
    n = 0
    buckets = []
    if isinstance(data.get("videos"), dict):
        buckets.append(data["videos"])
    if isinstance(data.get("files"), list):
        buckets.extend(data["files"])
    for bucket in buckets:
        items = bucket.values() if isinstance(bucket, dict) else bucket
        for item in items:
            if not isinstance(item, dict):
                continue
            p = item.get("path", "")
            base = os.path.basename(p)
            approved = os.path.join(RAW_APPROVED_VIDEO, base)
            pending = os.path.join(RAW_PENDING_VIDEO, base)
            new_p = None
            if os.path.isfile(approved):
                new_p = approved
            elif os.path.isfile(pending):
                new_p = pending
            if new_p and item.get("path") != new_p:
                item["path"] = new_p
                n += 1
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return n


def main() -> None:
    moved, kept = migrate_dirs()
    sync_n = fix_bilibili_sync()
    print(f"\n完成: {moved} 篇 → 已审阅视频文稿 | {kept} 篇留待审阅 | bilibili_sync 更新 {sync_n} 条")


if __name__ == "__main__":
    main()
