#!/usr/bin/env python3
"""
抖音（Douyin）视频文稿抓取 — 别名 fetch tiktok

博主默认：钱加贝（DOUYIN_SEC_UID / .env）

流程：列表 API → 下载音频 → SenseVoice 转录 → Raw/未审阅视频文稿/
后续：rw_video.py → txtcfm → ing（与 B 站相同）

用法:
  python douyin_fetch.py
  python douyin_fetch.py --since 2025-12-11
  python douyin_fetch.py --dry-run
  python douyin_fetch.py --max 3
"""
from __future__ import annotations

import argparse

from douyin.sync import default_since_days, sync_all


def main() -> None:
    p = argparse.ArgumentParser(description="抖音视频 ASR 抓取（fetch tiktok）")
    p.add_argument(
        "--since",
        default=None,
        help=f"只抓取该日期及之后 (YYYY-MM-DD)，默认近 180 天 ({default_since_days()})",
    )
    p.add_argument("--dry-run", action="store_true", help="只预览，不写文件")
    p.add_argument("--max", type=int, default=None, help="最多处理 N 条新视频")
    p.add_argument(
        "--skip-transcribe",
        action="store_true",
        help="仅测试列表/下载，跳过 ASR",
    )
    p.add_argument("--queue-file", default=None, help="从 JSON 队列抓取（浏览器导出 items 列表）")
    args = p.parse_args()

    stats = sync_all(
        since=args.since,
        dry_run=args.dry_run,
        max_videos=args.max,
        skip_transcribe=args.skip_transcribe,
        queue_file=args.queue_file,
    )
    print(
        f"\n完成: 新稿 {stats['videos']} | 跳过 {stats['skipped']} | "
        f"无转录 {stats['no_transcript']} | 错误 {stats['errors']}"
    )


if __name__ == "__main__":
    main()
