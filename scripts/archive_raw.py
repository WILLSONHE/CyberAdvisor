#!/usr/bin/env python3
"""
Raw 归档工具。

用法:
  python archive_raw.py migrate          # 一次性：根目录已消化 md → 已分析归档
  python archive_raw.py migrate-pending  # 根目录未消化 md → 未分析归档
  python archive_raw.py archive FILE     # 单篇 ing 完成后归档（视频稿→留已审阅）
  python archive_raw.py restore-videos   # 误归档视频稿 → 已审阅视频文稿
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

from raw_paths import (
    RAW_ARCHIVED,
    RAW_APPROVED_VIDEO,
    RAW_PENDING,
    RAW_PENDING_VIDEO,
    RAW_ROOT,
    ensure_raw_dirs,
    is_video_transcript,
    mark_video_ingested,
    restore_videos_from_archived,
)

# 明确未写入 Wiki、应留在待处理队列的文件名（log 2026-06-04）
PENDING_BASENAMES = {
    "复盘：26-05-18：5.18（复盘）.md",
}


def _is_skipped_dynamic(name: str) -> bool:
    return name.startswith("动态：26-06-04：")


def _unique_path(directory: str, filename: str) -> str:
    path = os.path.join(directory, filename)
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(filename)
    i = 2
    while True:
        alt = os.path.join(directory, f"{stem}_{i}{ext}")
        if not os.path.exists(alt):
            return alt
        i += 1


def _run_track_maintenance() -> None:
    """ing 归档后同步标的追踪目录（活跃池建页 / 非池归档）。"""
    from wiki import run_track_maintenance

    print("\n[track-maintain]")
    print(run_track_maintenance())


def archive_file(src: str, *, dry_run: bool = False) -> str:
    ensure_raw_dirs()
    if not os.path.isfile(src):
        raise FileNotFoundError(src)
    if is_video_transcript(src):
        dest = mark_video_ingested(src, dry_run=dry_run)
        label = "ingested (已审阅视频文稿)" if not dry_run else "ingested"
        print(f"  [OK] {os.path.basename(dest)} -> {label}")
        return dest
    dest = _unique_path(RAW_ARCHIVED, os.path.basename(src))
    if dry_run:
        print(f"  [DRY] {src} -> {dest}")
        return dest
    shutil.move(src, dest)
    print(f"  [OK] {os.path.basename(dest)}")
    return dest


def dedupe_pending_video(*, dry_run: bool = False) -> int:
    """未审阅目录中与已审阅同名的重复稿删除（保留已审阅）。"""
    ensure_raw_dirs()
    n = 0
    if not os.path.isdir(RAW_PENDING_VIDEO) or not os.path.isdir(RAW_APPROVED_VIDEO):
        return n
    approved = set(os.listdir(RAW_APPROVED_VIDEO))
    for name in os.listdir(RAW_PENDING_VIDEO):
        if name not in approved:
            continue
        src = os.path.join(RAW_PENDING_VIDEO, name)
        if dry_run:
            print(f"  [DRY] remove duplicate pending {name}")
        else:
            os.remove(src)
            print(f"  [OK] removed duplicate pending {name}")
        n += 1
    return n


def migrate_archived(*, dry_run: bool = False) -> int:
    """Raw 根目录下已消化 md → 已分析归档（排除未消化名单）。"""
    ensure_raw_dirs()
    n = 0
    for name in sorted(os.listdir(RAW_ROOT)):
        if not name.endswith(".md"):
            continue
        if name in PENDING_BASENAMES or _is_skipped_dynamic(name):
            continue
        src = os.path.join(RAW_ROOT, name)
        archive_file(src, dry_run=dry_run)
        n += 1
    return n


def migrate_pending(*, dry_run: bool = False) -> int:
    """Raw 根目录未消化 md → 未分析归档。"""
    ensure_raw_dirs()
    n = 0
    for name in sorted(os.listdir(RAW_ROOT)):
        if not name.endswith(".md"):
            continue
        if name not in PENDING_BASENAMES and not _is_skipped_dynamic(name):
            continue
        src = os.path.join(RAW_ROOT, name)
        dest = _unique_path(RAW_PENDING, name)
        if dry_run:
            print(f"  [DRY] {src} -> {dest}")
        else:
            shutil.move(src, dest)
            print(f"  [OK] pending {name}")
        n += 1
    return n


def main() -> None:
    p = argparse.ArgumentParser(description="Raw 归档")
    p.add_argument("--dry-run", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate", help="已消化 → 已分析归档")
    sub.add_parser("migrate-pending", help="未消化 → 未分析归档")
    sub.add_parser("restore-videos", help="已分析归档中的视频稿 → 已审阅视频文稿")
    sub.add_parser("dedupe-pending-video", help="删除未审阅中与已审阅重复的文件")
    ap = sub.add_parser("archive", help="单文件归档（视频留已审阅）")
    ap.add_argument("file", help="md 路径")
    args = p.parse_args()

    if args.cmd == "migrate":
        n = migrate_archived(dry_run=args.dry_run)
        print(f"已分析归档 +{n}")
        if n > 0 and not args.dry_run:
            _run_track_maintenance()
    elif args.cmd == "migrate-pending":
        n = migrate_pending(dry_run=args.dry_run)
        print(f"未分析归档 +{n}")
    elif args.cmd == "restore-videos":
        moved = restore_videos_from_archived(dry_run=args.dry_run)
        print(f"恢复视频稿 {len(moved)} 篇")
    elif args.cmd == "dedupe-pending-video":
        n = dedupe_pending_video(dry_run=args.dry_run)
        print(f"删除重复待审阅 {n} 篇")
    elif args.cmd == "archive":
        is_video = is_video_transcript(args.file)
        archive_file(args.file, dry_run=args.dry_run)
        if not args.dry_run:
            _run_track_maintenance()


if __name__ == "__main__":
    main()
