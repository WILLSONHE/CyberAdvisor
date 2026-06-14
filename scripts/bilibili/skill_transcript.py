"""bilibili-transcript skill 同款兜底：Web 页面 + player(aid/cid) + WBI player。"""
from __future__ import annotations

from typing import Any

import requests

from .client import BiliClient
from .env import BiliConfig
from .transcript import pick_subtitle
from .web_transcript import (
    _HEADERS,
    _download_subtitle_body,
    _normalize_bvid,
    _player_subtitles_via_api,
    _subtitle_tracks_from_html,
    fetch_transcript_via_web,
)


def check_login(cfg: BiliConfig | None = None) -> tuple[bool, str]:
    """nav code==0 且能读到 uname 视为 Cookie 有效。"""
    cfg = cfg or BiliConfig.load()
    session = requests.Session()
    session.trust_env = False
    session.headers.update(_HEADERS)
    session.headers["Cookie"] = cfg.cookie_header()
    try:
        resp = session.get("https://api.bilibili.com/x/web-interface/nav", timeout=20)
        payload = resp.json()
        code = payload.get("code")
        if code == 0:
            uname = (payload.get("data") or {}).get("uname") or ""
            return True, uname or "ok"
        if code == -101:
            return False, "Cookie 已失效（nav -101），请更新 .env 中 BILIBILI_SESSDATA / bili_jct / DedeUserID"
        return False, f"nav code={code} msg={payload.get('message')}"
    except Exception as exc:
        return False, str(exc)
    finally:
        session.close()


def _subs_from_player_json(data: dict[str, Any]) -> list[dict[str, Any]]:
    subs: list[dict[str, Any]] = []
    tracks = ((data.get("subtitle") or {}).get("subtitles")) or []
    session = requests.Session()
    session.trust_env = False
    session.headers.update(_HEADERS)
    for sub in tracks:
        url = sub.get("subtitle_url") or ""
        if not url:
            continue
        try:
            text = _download_subtitle_body(session, url)
        except Exception:
            continue
        if text.strip():
            subs.append(
                {
                    "lan": sub.get("lan") or "",
                    "lan_doc": sub.get("lan_doc") or "",
                    "ai": str(sub.get("lan") or "").startswith("ai-"),
                    "text": text,
                }
            )
    session.close()
    return subs


def _player_subtitles_aid(
    session: requests.Session,
    *,
    aid: int,
    cid: int,
    bvid: str,
) -> list[dict[str, Any]]:
    """skill / puppeteer 常用 aid+cid 调 player/v2。"""
    for ep in (
        "https://api.bilibili.com/x/player/wbi/v2",
        "https://api.bilibili.com/x/player/v2",
    ):
        try:
            params: dict[str, Any] = {"aid": aid, "cid": cid, "bvid": bvid}
            if "wbi" in ep:
                client = BiliClient(BiliConfig.load())
                try:
                    data = client._wbi_get(ep, params)  # noqa: SLF001
                finally:
                    client.close()
            else:
                r = session.get(ep, params=params, timeout=20)
                j = r.json()
                if j.get("code") not in (0, None):
                    continue
                data = j.get("data") or {}
            subs = _subs_from_player_json(data)
            if subs:
                return subs
        except Exception:
            continue
    return []


def fetch_transcript_via_skill(
    url_or_bvid: str,
    *,
    cfg: BiliConfig | None = None,
    title: str = "",
) -> tuple[str, str, str, list[dict[str, Any]]]:
    """
    bilibili-transcript skill 流程：
    1. 校验登录 Cookie
    2. view → aid/cid → player 字幕轨
    3. Web 页面 __INITIAL_STATE__ / player 兜底
    """
    cfg = cfg or BiliConfig.load()
    bvid = _normalize_bvid(url_or_bvid)
    ok, login_msg = check_login(cfg)
    if not ok:
        raise RuntimeError(login_msg)

    client = BiliClient(cfg)
    resolved_title = title or bvid
    charging = False
    try:
        view = client.video_view(bvid)
        resolved_title = title or view.get("title") or bvid
        charging = bool(view.get("is_upower_exclusive") or view.get("is_upower_play"))
        cid = int(view.get("cid") or 0)
        aid = int(view.get("aid") or 0)
        if cid:
            subs = client.video_subtitles(bvid, cid)
            if subs:
                lan, body = pick_subtitle(subs, resolved_title)
                if body and len(body.strip()) >= 30:
                    return resolved_title, lan, body, subs
            session = client.session
            subs = _player_subtitles_aid(session, aid=aid, cid=cid, bvid=bvid)
            if subs:
                lan, body = pick_subtitle(subs, resolved_title)
                if body and len(body.strip()) >= 30:
                    return resolved_title, lan, body, subs
            api_subs = _player_subtitles_via_api(session, bvid, cid, cookie=cfg.cookie_header())
            if api_subs:
                lan, body = pick_subtitle(api_subs, resolved_title)
                if body and len(body.strip()) >= 30:
                    return resolved_title, lan, body, api_subs
    finally:
        client.close()

    # Web 页面兜底（skill WebFetch 等价）
    try:
        lan, body, tracks = fetch_transcript_via_web(
            bvid, title=resolved_title, cookie=cfg.cookie_header()
        )
        if body and len(body.strip()) >= 30:
            return resolved_title, lan, body, tracks
    except Exception:
        pass

    hint = "UP 可能尚未生成 AI/CC 字幕（新片常需数小时）"
    if charging:
        hint = "充电专属视频需有效 Cookie + 充电会员权限；且 UP 需已生成 AI 字幕"
    raise RuntimeError(
        f"skill 兜底未找到字幕轨: {bvid} {resolved_title} | {hint} | "
        "请更新 .env Cookie 后重试：python bilibili_refetch_video.py " + bvid
    )
