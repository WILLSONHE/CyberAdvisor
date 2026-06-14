"""统一拉取 B 站视频字幕：API 优先，失败则 Web 兜底（bilibili-transcript skill 同款）。"""
from __future__ import annotations

from typing import Literal

from .client import BiliClient
from .env import BiliConfig
from .transcript import pick_subtitle
from .web_transcript import fetch_transcript_via_web

Source = Literal["api", "web"]


class TranscriptFetchError(RuntimeError):
    """API 与 Web 兜底均失败。"""


def fetch_transcript(
    bvid: str,
    *,
    cfg: BiliConfig | None = None,
    title: str = "",
) -> tuple[str, str, str, Source]:
    """
    返回 (title, lang, raw_body, source)。
    1. BiliClient player/wbi 字幕 API
    2. Web 页面 + 字幕 JSON（skill 兜底）
    """
    cfg = cfg or BiliConfig.load()
    bvid = bvid.strip()
    client = BiliClient(cfg)
    api_err = ""
    try:
        view = client.video_view(bvid)
        resolved_title = title or view.get("title") or bvid
        cid = view.get("cid")
        if not cid:
            raise TranscriptFetchError(f"无 cid: {bvid}")
        subs = client.video_subtitles(bvid, cid)
        if subs:
            lan, raw = pick_subtitle(subs, resolved_title)
            if raw and len(raw.strip()) >= 30:
                return resolved_title, lan, raw, "api"
        api_err = "API 无有效字幕轨"
    except Exception as exc:
        api_err = str(exc)
    finally:
        client.close()

    try:
        lan, raw, _tracks = fetch_transcript_via_web(
            bvid,
            title=title,
            cookie=cfg.cookie_header(),
        )
        resolved_title = title or bvid
        return resolved_title, lan, raw, "web"
    except Exception as web_exc:
        hint = (
            "请确认 UP 已开启 AI/CC 字幕，并在 .env 更新有效的 "
            "BILIBILI_SESSDATA / bili_jct / DedeUserID（未登录时字幕列表为空）。"
        )
        raise TranscriptFetchError(
            f"{bvid} 字幕抓取失败 | API: {api_err} | Web: {web_exc} | {hint}"
        ) from web_exc
