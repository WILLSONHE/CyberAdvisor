#!/usr/bin/env python3
"""
重拉单个 B 站视频字幕并写回 Raw/未审阅视频文稿/。

用法:
  python bilibili_refetch_video.py BV1auEt61EJj
  python bilibili_refetch_video.py BV1auEt61EJj --path "Raw/未审阅视频文稿/xxx.md"
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

from bilibili.asr_fixes import apply_asr_fixes
from bilibili.client import BiliClient
from bilibili.env import BiliConfig, ROOT
from bilibili.rw_format import format_transcript
from bilibili.sync import _frontmatter, _load_state, _save_state
from bilibili.transcript import pick_subtitle, score_subtitle
from raw_paths import RAW_PENDING_VIDEO

META_BVID = re.compile(r"^bvid:\s*(\S+)", re.M)


def _find_path_by_bvid(bvid: str) -> str | None:
    if not os.path.isdir(RAW_PENDING_VIDEO):
        return None
    for name in os.listdir(RAW_PENDING_VIDEO):
        if bvid in name and name.endswith(".md"):
            return os.path.join(RAW_PENDING_VIDEO, name)
    return None


def refetch_video(bvid: str, *, path: str | None = None, dry_run: bool = False) -> str:
    cfg = BiliConfig.load()
    client = BiliClient(cfg)
    try:
        view = client.video_view(bvid)
        title = view.get("title") or bvid
        cid = view.get("cid")
        if not cid:
            raise SystemExit(f"无 cid: {bvid}")
        subs = client.video_subtitles(bvid, cid)
        if not subs:
            raise SystemExit(f"无字幕轨: {bvid} {title}")
        lan, raw = pick_subtitle(subs, title)
        if not raw or len(raw.strip()) < 30:
            raise SystemExit(f"字幕正文过短: {bvid} len={len(raw)}")
        body = format_transcript(raw, force_punctuate=True)
        body, _ = apply_asr_fixes(body)
        score = score_subtitle(body, title)
        if score < 8 and looks_like_mismatch(body, title):
            print(f"[WARN] 字幕与标题可能不匹配 score={score}")

        target = path or _find_path_by_bvid(bvid)
        if not target:
            raise SystemExit(f"未找到待审阅 md，请用 --path 指定: {bvid}")

        pub_ts = int(view.get("pubdate") or 0)
        pub_date = datetime.fromtimestamp(pub_ts).strftime("%Y-%m-%d") if pub_ts else ""
        content = _frontmatter({
            "bvid": bvid,
            "title": title,
            "source": "bilibili",
            "type": "video_transcript",
            "subtitle_lang": lan,
            "pub_time": pub_date,
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "refetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "review_status": "rewritten",
            "rw_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        content += f"# {title}\n\n> B站视频字幕稿（待审阅）| {bvid}\n\n{body}\n"

        if dry_run:
            print(f"[DRY-RUN] {target} ({len(body)} chars)")
            return target

        with open(target, "w", encoding="utf-8") as f:
            f.write(content)

        state = _load_state()
        state.setdefault("videos", {})[bvid] = {
            "path": os.path.abspath(target),
            "fetched_at": datetime.now().isoformat(),
        }
        _save_state(state)
        print(f"[OK] {os.path.basename(target)} | {len(body)} 字 | lang={lan}")
        return target
    finally:
        client.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="重拉单个 B 站视频字幕")
    ap.add_argument("bvid", help="BV 号")
    ap.add_argument("--path", default="", help="目标 md 路径")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    bvid = args.bvid.strip()
    if not bvid.upper().startswith("BV"):
        raise SystemExit("需要 BV 开头的 bvid")
    path = args.path.strip() or None
    if path and not os.path.isabs(path):
        path = os.path.join(ROOT, path)
    refetch_video(bvid, path=path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
