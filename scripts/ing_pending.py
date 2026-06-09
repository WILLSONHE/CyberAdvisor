#!/usr/bin/env python3
"""
ing 待处理队列一览（专栏 + 视频 + 其他材料）。

用法:
  python ing_pending.py              # 人类可读摘要
  python ing_pending.py --json       # Agent 结构化输出
  python ing_pending.py backfill-video-meta   # 从已有视频专题页反填 raw frontmatter
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from raw_paths import list_pending_files, list_pending_material_files  # noqa: E402
from wiki.video_topic import (  # noqa: E402
    backfill_wiki_topic_meta,
    list_video_ing_pending,
)


def collect_pending() -> dict:
    column = [
        os.path.relpath(p, ROOT).replace("\\", "/") for p in list_pending_files()
    ]
    materials = [
        os.path.relpath(p, ROOT).replace("\\", "/")
        for p in list_pending_material_files()
    ]
    videos = list_video_ing_pending()
    return {
        "column_dynamic": column,
        "video": videos,
        "materials": materials,
        "counts": {
            "column_dynamic": len(column),
            "video": len(videos),
            "materials": len(materials),
        },
    }


def print_human(data: dict) -> None:
    c = data["counts"]
    print(f"# ing 待处理队列 ({c['column_dynamic'] + c['video'] + c['materials']} 项)\n")

    print("## 专栏/动态 (Raw/未分析归档/)")
    if data["column_dynamic"]:
        for p in data["column_dynamic"]:
            print(f"  - {p}")
    else:
        print("  (空)")

    print("\n## 已审阅视频文稿 (Raw/已审阅视频文稿/)")
    if data["video"]:
        for v in data["video"]:
            tasks = "+".join(v["tasks"])
            print(f"  - [{tasks}] {v['relpath']}")
            print(f"      title: {v.get('title', '')} | bvid: {v.get('bvid', '')}")
            print(f"      → 建议专题: {v['suggested_wiki_topic']} ({v['suggested_category']})")
    else:
        print("  (空 — 日更与视频专题均已同步)")

    print("\n## 其他材料 (Raw/未分析其他材料/)")
    if data["materials"]:
        for p in data["materials"]:
            print(f"  - {p}")
    else:
        print("  (空)")


def main() -> int:
    parser = argparse.ArgumentParser(description="ing 待处理队列")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument(
        "command",
        nargs="?",
        choices=("backfill-video-meta",),
        help="维护命令",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.command == "backfill-video-meta":
        pairs = backfill_wiki_topic_meta(dry_run=args.dry_run)
        for raw, wiki in pairs:
            tag = "DRY" if args.dry_run else "OK"
            print(f"  [{tag}] {os.path.basename(raw)} → {wiki}")
        print(f"\n{len(pairs)} raw file(s) {'would be ' if args.dry_run else ''}updated")
        return 0

    data = collect_pending()
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print_human(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
