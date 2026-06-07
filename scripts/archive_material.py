#!/usr/bin/env python3
"""
其他材料归档：ing 完成后移入 Raw/已分析其他材料/。

用法:
  python archive_material.py archive FILE
  python archive_material.py archive-all   # 移走未分析目录下全部已支持格式
"""
from __future__ import annotations

import argparse
import os
import shutil

from raw_paths import (
    RAW_ARCHIVED_MATERIALS,
    RAW_PENDING_MATERIALS,
    ensure_raw_dirs,
    list_pending_material_files,
)


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
    pending = os.path.normpath(RAW_PENDING_MATERIALS)
    if os.path.normpath(os.path.dirname(os.path.abspath(src))) != pending:
        raise ValueError(f"仅归档 {pending} 下的文件: {src}")
    dest = _unique_path(RAW_ARCHIVED_MATERIALS, os.path.basename(src))
    if dry_run:
        print(f"  [DRY] {src} -> {dest}")
        return dest
    shutil.move(src, dest)
    print(f"  [OK] {os.path.basename(dest)}")
    return dest


def archive_all(*, dry_run: bool = False) -> int:
    files = list_pending_material_files()
    for src in files:
        archive_file(src, dry_run=dry_run)
    return len(files)


def main() -> None:
    ap = argparse.ArgumentParser(description="其他材料归档")
    ap.add_argument("--dry-run", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("archive-all", help="归档未分析其他材料目录下全部文件")
    ar = sub.add_parser("archive", help="归档单个文件")
    ar.add_argument("file", help="源文件路径")
    args = ap.parse_args()
    if args.cmd == "archive":
        archive_file(args.file, dry_run=args.dry_run)
    elif args.cmd == "archive-all":
        n = archive_all(dry_run=args.dry_run)
        print(f"已分析其他材料 +{n}")


if __name__ == "__main__":
    main()
