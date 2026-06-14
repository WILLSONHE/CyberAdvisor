"""写入 B 站视频字幕稿到 Raw/未审阅视频文稿/。"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from .env import ROOT
from .fetch_transcript import TranscriptFetchError, fetch_transcript
from .naming import pending_video_filename
from .rw_format import format_transcript
from .sync import (
    PENDING_DIR,
    _frontmatter,
    _load_state,
    _save_state,
    _unique_path,
    _write,
)


def write_video_transcript(
    bvid: str,
    *,
    path: str | None = None,
    dry_run: bool = False,
    pub_ts: int | None = None,
) -> dict[str, Any]:
    """拉取字幕（API→Web 兜底）并写入 md。返回 {path, title, source, chars}。"""
    from .asr_fixes import apply_asr_fixes
    from .env import BiliConfig

    cfg = BiliConfig.load()
    title, lan, raw, src = fetch_transcript(bvid, cfg=cfg)
    body = format_transcript(raw, force_punctuate=True)
    body, _ = apply_asr_fixes(body)

    if not pub_ts:
        from .client import BiliClient

        client = BiliClient(cfg)
        try:
            view = client.video_view(bvid)
            pub_ts = int(view.get("pubdate") or 0)
            title = view.get("title") or title
        finally:
            client.close()

    fname = pending_video_filename(title, bvid, pub_ts or None)
    target = path or _unique_path(PENDING_DIR, fname)
    pub_date = datetime.fromtimestamp(pub_ts).strftime("%Y-%m-%d") if pub_ts else ""
    content = _frontmatter(
        {
            "bvid": bvid,
            "title": title,
            "source": "bilibili",
            "type": "video_transcript",
            "subtitle_lang": lan,
            "subtitle_via": src,
            "pub_time": pub_date,
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "review_status": "pending",
        }
    )
    content += f"# {title}\n\n> B站视频字幕稿（待审阅）| {bvid} | via {src}\n\n{body}\n"

    _write(target, content, dry_run)
    if not dry_run:
        state = _load_state()
        state.setdefault("videos", {})[bvid] = {
            "path": os.path.abspath(target),
            "fetched_at": datetime.now().isoformat(),
            "subtitle_via": src,
        }
        _save_state(state)
    return {
        "path": target,
        "title": title,
        "source": src,
        "chars": len(body),
        "lang": lan,
    }


def refetch_video_md(
    bvid: str,
    *,
    path: str | None = None,
    dry_run: bool = False,
) -> str:
    try:
        result = write_video_transcript(bvid, path=path, dry_run=dry_run)
    except TranscriptFetchError as exc:
        raise SystemExit(str(exc)) from exc
    print(
        f"[OK] {os.path.basename(result['path'])} | {result['chars']} 字 | "
        f"lang={result['lang']} | via={result['source']}"
    )
    return result["path"]
