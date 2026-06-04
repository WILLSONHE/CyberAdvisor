#!/usr/bin/env python3
"""
B 站博主内容抓取（青枫浦上Q）

- 视频字幕 → Wiki/待审阅视频文稿/（自动）→ rw → txtcfm → ing
- 专栏/动态/充电文 → 手动复制 md 到 Raw/未分析归档/ → ing

用法:
  python bilibili_fetch.py
  python bilibili_fetch.py --since 2026-05-14
  python bilibili_fetch.py --dry-run
"""
from __future__ import annotations

import argparse

from bilibili.sync import sync_all


def main() -> None:
    p = argparse.ArgumentParser(description="B站视频字幕抓取（专栏/动态请手动归档）")
    p.add_argument("--since", default="2026-05-14", help="只抓取该日期及之后的视频 (YYYY-MM-DD)")
    p.add_argument("--dry-run", action="store_true", help="只预览，不写文件")
    args = p.parse_args()

    stats = sync_all(
        since=args.since,
        dry_run=args.dry_run,
        videos=True,
        dynamics=False,
        articles=False,
    )
    print(
        f"\n完成: 视频 {stats['videos']} | 无字幕 {stats['no_subtitle']} | "
        f"跳过 {stats['skipped']}"
    )


if __name__ == "__main__":
    main()
