#!/usr/bin/env python3
"""
Raw 归档工具。

用法:
  python archive_raw.py migrate          # 一次性：根目录已消化 md → 已分析归档
  python archive_raw.py migrate-pending  # 根目录未消化 md → 未分析归档
  python archive_raw.py archive FILE     # 单篇 ing 完成后移入已分析归档
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

from raw_paths import RAW_ARCHIVED, RAW_PENDING, RAW_ROOT, ensure_raw_dirs

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


def archive_file(src: str, *, dry_run: bool = False) -> str:
    ensure_raw_dirs()
    if not os.path.isfile(src):
        raise FileNotFoundError(src)
    dest = _unique_path(RAW_ARCHIVED, os.path.basename(src))
    if dry_run:
        print(f"  [DRY] {src} -> {dest}")
        return dest
    shutil.move(src, dest)
    print(f"  [OK] {os.path.basename(dest)}")
    return dest


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
    ap = sub.add_parser("archive", help="单文件 → 已分析归档")
    ap.add_argument("file", help="md 路径")
    args = p.parse_args()

    if args.cmd == "migrate":
        n = migrate_archived(dry_run=args.dry_run)
        print(f"已分析归档 +{n}")
    elif args.cmd == "migrate-pending":
        n = migrate_pending(dry_run=args.dry_run)
        print(f"未分析归档 +{n}")
    elif args.cmd == "archive":
        archive_file(args.file, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
