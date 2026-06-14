#!/usr/bin/env python3
"""对 missing_dawan 列表批量用 transcript 通道（API→Web/skill 同款）抓取并写入 Raw。"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from bilibili.asr_fixes import looks_like_mismatch
from bilibili.client import BiliClient
from bilibili.env import BiliConfig, BiliUp
from bilibili.fetch_transcript import TranscriptFetchError, fetch_transcript
from bilibili.naming import pending_video_filename
from bilibili.rw_format import format_transcript
from bilibili.sync import (
    PENDING_DIR,
    _frontmatter,
    _load_state,
    _save_state,
    _unique_path,
    _view_is_free,
)
from raw_paths import RAW_PENDING_VIDEO

MISSING_PATH = os.path.join(ROOT, "Wiki", "数据", "missing_dawan_518715314.json")
UP = BiliUp("518715314", "大弯区董事长")


def main() -> None:
    missing = json.load(open(MISSING_PATH, encoding="utf-8"))
    cfg = BiliConfig.load().with_up(UP)
    client = BiliClient(cfg)
    state = _load_state()
    results = {"ok": [], "skip": [], "fail": []}

    for item in missing:
        bvid = item["bvid"]
        title = item["title"]
        pub_ts = item.get("created", 0)
        print(f"\n=== {bvid} | {title}")

        try:
            view = client.video_view(bvid)
        except RuntimeError as e:
            if "code=-404" in str(e):
                print("  [404] 视频已下架")
                results["skip"].append({"bvid": bvid, "title": title, "reason": "404"})
                continue
            print(f"  [ERR] view: {e}")
            results["fail"].append({"bvid": bvid, "title": title, "reason": str(e)})
            continue
        except Exception as e:
            print(f"  [ERR] view: {e}")
            results["fail"].append({"bvid": bvid, "title": title, "reason": str(e)})
            continue

        title = view.get("title") or title
        pub_ts = int(view.get("pubdate") or pub_ts or 0)
        if not _view_is_free(view):
            print("  [SKIP] 充电/专属")
            results["skip"].append({"bvid": bvid, "title": title, "reason": "paywalled"})
            continue

        try:
            title, lan, body, src = fetch_transcript(bvid, cfg=cfg, title=title)
        except TranscriptFetchError as e:
            print(f"  [FAIL] {e}")
            results["fail"].append({"bvid": bvid, "title": title, "reason": str(e)})
            continue

        if not body or len(body.strip()) < 30:
            print("  [FAIL] 正文过短")
            results["fail"].append({"bvid": bvid, "title": title, "reason": "empty"})
            continue

        if looks_like_mismatch(body, title, subtitle_via=src):
            print("  [FAIL] 字幕与标题不符")
            results["fail"].append({"bvid": bvid, "title": title, "reason": "mismatch"})
            continue

        body = format_transcript(body, force_punctuate=True)
        fname = pending_video_filename(title, bvid, pub_ts or None)
        path = _unique_path(PENDING_DIR, fname)
        pub_date = datetime.fromtimestamp(pub_ts).strftime("%Y-%m-%d") if pub_ts else ""
        meta = {
            "bvid": bvid,
            "title": title,
            "source": "bilibili",
            "type": "video_transcript",
            "subtitle_lang": lan,
            "subtitle_via": src,
            "pub_time": pub_date,
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "review_status": "pending",
            "up_mid": UP.mid,
            "creator": UP.name,
        }
        content = _frontmatter(meta)
        content += f"# {title}\n\n> B站视频字幕稿（待审阅）| {bvid}\n\n{body}\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        state["videos"][bvid] = {
            "path": path,
            "fetched_at": datetime.now().isoformat(),
            "up_mid": UP.mid,
            "creator": UP.name,
        }
        print(f"  [OK] {os.path.basename(path)} via {src} ({len(body)} chars)")
        results["ok"].append({"bvid": bvid, "title": title, "path": path, "via": src})
        time.sleep(0.6)

    client.close()
    _save_state(state)
    out = os.path.join(ROOT, "Wiki", "数据", "missing_dawan_fetch_result.json")
    json.dump(results, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(
        f"\n完成: 成功 {len(results['ok'])} | 跳过 {len(results['skip'])} | "
        f"失败 {len(results['fail'])}"
    )


if __name__ == "__main__":
    main()
