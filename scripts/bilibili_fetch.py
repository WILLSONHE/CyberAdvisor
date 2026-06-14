#!/usr/bin/env python3

"""

B 站内容源抓取（多 UP，见 .env BILIBILI_UPS）



- 视频字幕 → Raw/未审阅视频文稿/（自动）→ rw → txtcfm → ing

- 专栏/动态/充电文 → 手动复制 md 到 Raw/未分析归档/ → ing



用法:

  python bilibili_fetch.py

  python bilibili_fetch.py --since 2026-05-14

  python bilibili_fetch.py --mid 518715314 --since 2020-01-01

  python bilibili_fetch.py --dry-run

"""

from __future__ import annotations



import argparse



from bilibili.sync import sync_all





def main() -> None:

    p = argparse.ArgumentParser(description="B站视频字幕抓取（专栏/动态请手动归档）")

    p.add_argument("--since", default="2026-05-14", help="只抓取该日期及之后的视频 (YYYY-MM-DD)")

    p.add_argument("--mid", default="", help="仅抓取指定 UP 的 mid（须在 BILIBILI_UPS 中）")

    p.add_argument(

        "--free-only",

        action=argparse.BooleanOptionalAction,

        default=True,

        help="仅抓取免费公开视频（默认开启）",

    )

    p.add_argument("--title", default="", help="仅抓取标题包含该字符串的视频")

    p.add_argument("--dry-run", action="store_true", help="只预览，不写文件")

    args = p.parse_args()



    stats = sync_all(

        since=args.since,

        dry_run=args.dry_run,

        videos=True,

        dynamics=False,

        articles=False,

        title_match=args.title.strip(),

        mid=args.mid.strip() or None,

        free_only=args.free_only,

    )

    print(

        f"\n完成: 视频 {stats['videos']} | 无字幕 {stats['no_subtitle']} | "

        f"付费跳过 {stats['paid_skipped']} | 跳过 {stats['skipped']}"

    )





if __name__ == "__main__":

    main()

