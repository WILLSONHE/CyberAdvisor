"""抖音视频文稿同步：列表 → 下载 → SenseVoice → Raw/未审阅视频文稿/。"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime, timedelta
from typing import Any, Iterator

from bilibili.rw_format import format_transcript

from .client import DouyinClient
from .download import download_audio
from .env import ROOT, DouyinConfig
from .naming import pending_douyin_filename
from .transcribe import transcribe_audio

RAW_DIR = os.path.join(ROOT, "Raw")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from raw_paths import RAW_PENDING_VIDEO  # noqa: E402

PENDING_DIR = RAW_PENDING_VIDEO
STATE_PATH = os.path.join(ROOT, "Wiki", "数据", "douyin_sync.json")

META_AWEME = re.compile(r"^aweme_id:\s*(\S+)", re.M)


def _ensure_dirs() -> None:
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(PENDING_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)


def _load_state() -> dict:
    if os.path.isfile(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"videos": {}, "creator": "", "sec_uid": ""}


def _save_state(state: dict) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _scan_existing_aweme_ids() -> set[str]:
    ids: set[str] = set()
    for folder in (RAW_DIR, PENDING_DIR):
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            if not name.endswith(".md"):
                continue
            path = os.path.join(folder, name)
            try:
                head = open(path, encoding="utf-8").read(800)
            except OSError:
                continue
            m = META_AWEME.search(head)
            if m:
                ids.add(m.group(1))
            # 文件名中含 aweme_id
            for part in name.split("_"):
                if part.isdigit() and len(part) >= 15:
                    ids.add(part)
    return ids


def _parse_since(since: str | None) -> int:
    if not since:
        return 0
    since = since.strip()
    for fmt in ("%Y-%m-%d", "%y-%m-%d"):
        try:
            return int(datetime.strptime(since, fmt).timestamp())
        except ValueError:
            continue
    raise ValueError(f"无效 --since 日期: {since}")


def default_since_days(days: int = 180) -> str:
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")


def _frontmatter(meta: dict[str, Any]) -> str:
    lines = ["---"]
    for k, v in meta.items():
        lines.append(f"{k}: {v}")
    lines.append("---\n")
    return "\n".join(lines)


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


def _safe_print(msg: str) -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("gbk", errors="replace").decode("gbk"), flush=True)


def _load_queue_file(path: str) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return list(data.get("items") or [])


def _iter_videos_from_sources(
    cfg: DouyinConfig,
    *,
    queue_file: str | None,
) -> Iterator[dict[str, Any]]:
    if queue_file:
        for item in _load_queue_file(queue_file):
            yield item
        return
    client = DouyinClient(sec_uid=cfg.sec_uid, cookie=cfg.cookie)
    try:
        yield from client.iter_videos()
    finally:
        client.close()


def _write(path: str, content: str, dry_run: bool) -> None:
    if dry_run:
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def sync_all(
    *,
    since: str | None = None,
    dry_run: bool = False,
    max_videos: int | None = None,
    skip_transcribe: bool = False,
    queue_file: str | None = None,
) -> dict[str, int]:
    _ensure_dirs()
    cfg = DouyinConfig.load()
    if cfg.source == "missing" and not queue_file:
        _safe_print(
            "[WARN] 缺少 DOUYIN_COOKIE，跳过抖音抓取。"
            "请配置 .env 或 secrets/douyin.cookie（DevTools Network 完整 Cookie），"
            "或使用 --queue-file。"
        )
        return {"videos": 0, "skipped": 0, "no_transcript": 0, "errors": 0}

    if since is None:
        since = default_since_days(180)

    since_ts = _parse_since(since)
    state = _load_state()
    state.setdefault("videos", {})
    state["creator"] = cfg.creator
    state["sec_uid"] = cfg.sec_uid

    known = _scan_existing_aweme_ids()
    known.update(state["videos"].keys())

    stats = {"videos": 0, "skipped": 0, "no_transcript": 0, "errors": 0}

    _safe_print(
        f"配置: 博主={cfg.creator} | sec_uid={cfg.sec_uid[:20]}… | "
        f"cookie={cfg.source} | since={since}"
        + (f" | queue={queue_file}" if queue_file else "")
    )
    _safe_print(f"\n[抖音] 拉取作品 + SenseVoice 转录 → {PENDING_DIR}")

    processed = 0
    try:
        for v in _iter_videos_from_sources(cfg, queue_file=queue_file):
            aweme_id = v.get("aweme_id") or ""
            if not aweme_id or aweme_id in known:
                stats["skipped"] += 1
                continue
            pub_ts = int(v.get("create_time") or 0)
            if since_ts and pub_ts and pub_ts < since_ts:
                stats["skipped"] += 1
                continue
            title = v.get("title") or aweme_id

            if dry_run:
                pub_date = datetime.fromtimestamp(pub_ts).strftime("%Y-%m-%d") if pub_ts else "?"
                _safe_print(f"  [DRY] {pub_date} {title[:50]} ({aweme_id})")
                stats["videos"] += 1
                known.add(aweme_id)
                processed += 1
                if max_videos and processed >= max_videos:
                    break
                continue

            tmpdir = tempfile.mkdtemp(prefix="dyt-sync-")
            try:
                audio_path = ""
                dl_title = title
                for dl_try in range(3):
                    try:
                        _safe_print(
                            f"  [FETCH] {title[:50]} ({aweme_id})"
                            + (f" retry={dl_try}" if dl_try else "")
                        )
                        audio_path, dl_title = download_audio(aweme_id, tmpdir)
                        break
                    except Exception as e:
                        if dl_try >= 2:
                            raise
                        _safe_print(f"  [RETRY] {aweme_id}: {e}")
                        time.sleep(2.0 * (dl_try + 1))
                title = dl_title or title
                transcriber = "SenseVoice-Small"
                if skip_transcribe:
                    body = ""
                else:
                    raw_text, transcriber = transcribe_audio(audio_path)
                    body = format_transcript(raw_text, force_punctuate=True)
                if not body or len(body.strip()) < 30:
                    _safe_print(f"  [SKIP] {aweme_id} 转录过短或无内容")
                    stats["no_transcript"] += 1
                    continue

                fname = pending_douyin_filename(title, aweme_id, pub_ts)
                path = _unique_path(PENDING_DIR, fname)
                pub_date = datetime.fromtimestamp(pub_ts).strftime("%Y-%m-%d") if pub_ts else ""
                content = _frontmatter(
                    {
                        "aweme_id": aweme_id,
                        "title": title,
                        "source": "douyin",
                        "creator": cfg.creator,
                        "type": "video_transcript",
                        "transcriber": transcriber if not skip_transcribe else "skipped",
                        "pub_time": pub_date,
                        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "review_status": "pending",
                    }
                )
                content += (
                    f"# {title}\n\n"
                    f"> 抖音视频 ASR 稿（待审阅）| {cfg.creator} | {aweme_id}\n\n"
                    f"{body}\n"
                )
                _write(path, content, dry_run=False)
                _safe_print(f"  [NEW] {os.path.basename(path)}")
                state["videos"][aweme_id] = {
                    "path": path,
                    "title": title,
                    "fetched_at": datetime.now().isoformat(),
                }
                known.add(aweme_id)
                stats["videos"] += 1
                processed += 1
                time.sleep(0.8)
            except Exception as e:
                stats["errors"] += 1
                _safe_print(f"  [ERR] {aweme_id}: {e}")
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)

            if max_videos and processed >= max_videos:
                break
    finally:
        if not dry_run:
            _save_state(state)

    return stats
