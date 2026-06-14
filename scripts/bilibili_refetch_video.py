#!/usr/bin/env python3
"""
重拉单个 B 站视频字幕并写回 Raw/未审阅视频文稿/。
API 失败时自动走 Web/transcript skill 兜底。

用法:
  python bilibili_refetch_video.py BV1auEt61EJj
  python bilibili_refetch_video.py BV1fwEC6vEXL
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from bilibili.env import ROOT
from bilibili.video_io import refetch_video_md
from raw_paths import RAW_PENDING_VIDEO

META_BVID = re.compile(r"^bvid:\s*(\S+)", re.M)


def _find_path_by_bvid(bvid: str) -> str | None:
    if not os.path.isdir(RAW_PENDING_VIDEO):
        return None
    for name in os.listdir(RAW_PENDING_VIDEO):
        if bvid in name and name.endswith(".md"):
            return os.path.join(RAW_PENDING_VIDEO, name)
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description="重拉单个 B 站视频字幕（含 Web 兜底）")
    ap.add_argument("bvid", help="BV 号")
    ap.add_argument("--path", default="", help="目标 md 路径")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    bvid = args.bvid.strip()
    if not bvid.upper().startswith("BV"):
        raise SystemExit("需要 BV 开头的 bvid")
    path = args.path.strip() or _find_path_by_bvid(bvid) or ""
    if path and not os.path.isabs(path):
        path = os.path.join(ROOT, path)
    refetch_video_md(bvid, path=path or None, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
