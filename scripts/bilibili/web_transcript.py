"""B 站字幕 Web 抓取兜底（API 无字幕轨时，对齐 bilibili-transcript skill：页面/Web 字幕）。"""
from __future__ import annotations

import json
import re
import sys
from typing import Any
from urllib.parse import urljoin

import requests

SCRIPT_DIR = __import__("os").path.dirname(__import__("os").path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from .transcript import pick_subtitle

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}


def _normalize_bvid(url_or_bvid: str) -> str:
    s = url_or_bvid.strip()
    m = re.search(r"(BV[0-9A-Za-z]+)", s, re.I)
    if m:
        return m.group(1)
    if s.upper().startswith("BV"):
        return s
    raise ValueError(f"无法解析 BV 号: {url_or_bvid}")


def _extract_json_blob(html: str, marker: str) -> dict[str, Any] | None:
    idx = html.find(marker)
    if idx < 0:
        return None
    start = html.find("{", idx)
    if start < 0:
        return None
    depth = 0
    for i in range(start, min(len(html), start + 800_000)):
        ch = html[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _subtitle_tracks_from_html(html: str) -> list[dict[str, Any]]:
    tracks: list[dict[str, Any]] = []
    for blob in (
        _extract_json_blob(html, "window.__INITIAL_STATE__"),
        _extract_json_blob(html, "window.__playinfo__"),
    ):
        if not blob:
            continue
        # __INITIAL_STATE__: videoData.subtitle.list
        vd = blob.get("videoData") or {}
        sub = vd.get("subtitle") or {}
        for item in sub.get("list") or []:
            url = item.get("subtitle_url") or item.get("url") or ""
            if url:
                tracks.append(
                    {
                        "lan": item.get("lan") or item.get("lang") or "",
                        "lan_doc": item.get("lan_doc") or item.get("lang_doc") or "",
                        "ai": str(item.get("type") or "") == "1",
                        "subtitle_url": url,
                    }
                )
        # playinfo data.dash or data.subtitle
        data = blob.get("data") or blob
        for item in (data.get("subtitle") or {}).get("subtitles") or []:
            url = item.get("subtitle_url") or ""
            if url:
                tracks.append(
                    {
                        "lan": item.get("lan") or "",
                        "lan_doc": item.get("lan_doc") or "",
                        "ai": str(item.get("lan") or "").startswith("ai-"),
                        "subtitle_url": url,
                    }
                )
        # dedupe by url — 禁止全页 regex 抓推荐位字幕（易错配）
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for t in tracks:
        u = t.get("subtitle_url") or ""
        if u in seen:
            continue
        seen.add(u)
        out.append(t)
    return out


def _download_subtitle_body(session: requests.Session, url: str) -> str:
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/"):
        url = urljoin("https://api.bilibili.com", url)
    resp = session.get(url, headers=_HEADERS, timeout=25)
    resp.raise_for_status()
    data = resp.json()
    body = data.get("body") or []
    return "".join(item.get("content", "") for item in body)


def _player_subtitles_via_api(
    session: requests.Session,
    bvid: str,
    cid: int,
    *,
    cookie: str = "",
) -> list[dict[str, Any]]:
    """player/wbi/v2 + v2（需 Cookie 才有 ai-zh 轨）。"""
    if cookie:
        session.headers["Cookie"] = cookie
    subs: list[dict[str, Any]] = []
    for ep in (
        "https://api.bilibili.com/x/player/wbi/v2",
        "https://api.bilibili.com/x/player/v2",
    ):
        try:
            r = session.get(
                ep,
                params={
                    "bvid": bvid,
                    "cid": cid,
                    "isGaiaAvoided": "false",
                    "web_location": 1315873,
                },
                timeout=20,
            )
            j = r.json()
            tracks = ((j.get("data") or {}).get("subtitle") or {}).get("subtitles") or []
            for sub in tracks:
                url = sub.get("subtitle_url") or ""
                if not url:
                    continue
                text = _download_subtitle_body(session, url)
                if text.strip():
                    subs.append(
                        {
                            "lan": sub.get("lan") or "",
                            "lan_doc": sub.get("lan_doc") or "",
                            "ai": str(sub.get("lan") or "").startswith("ai-"),
                            "text": text,
                        }
                    )
            if subs:
                return subs
        except Exception:
            continue
    return subs


def fetch_transcript_via_web(
    url_or_bvid: str,
    *,
    title: str = "",
    cookie: str = "",
) -> tuple[str, str, list[dict[str, Any]]]:
    """
    返回 (lang, body, raw_tracks)。
    对齐 bilibili-transcript skill：Web 侧抓取字幕 JSON。
    """
    bvid = _normalize_bvid(url_or_bvid)
    session = requests.Session()
    session.trust_env = False
    session.headers.update(_HEADERS)
    if cookie:
        session.headers["Cookie"] = cookie

    page_url = f"https://www.bilibili.com/video/{bvid}"
    html = session.get(page_url, timeout=25).text
    if not title:
        m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        title = (m.group(1).split("_")[0] if m else bvid).strip()
        title = title.replace("&quot;", '"').replace("&#34;", '"')

    # player API（登录 Cookie 下常有 ai-zh）
    cid = None
    m_cid = re.search(r'"cid"\s*:\s*(\d+)', html)
    if m_cid:
        cid = int(m_cid.group(1))
    if cid:
        api_subs = _player_subtitles_via_api(session, bvid, cid, cookie=cookie)
        if api_subs:
            lan, body = pick_subtitle(api_subs, title)
            if body and len(body.strip()) >= 30:
                return lan, body, api_subs

    tracks = _subtitle_tracks_from_html(html)
    subs: list[dict[str, Any]] = []
    for t in tracks:
        url = t.get("subtitle_url") or ""
        if not url:
            continue
        try:
            text = _download_subtitle_body(session, url)
        except Exception:
            continue
        if text.strip():
            subs.append(
                {
                    "lan": t.get("lan") or "",
                    "lan_doc": t.get("lan_doc") or "",
                    "ai": t.get("ai", False),
                    "text": text,
                }
            )

    if not subs:
        raise RuntimeError(f"Web 字幕兜底未找到字幕轨: {bvid} {title}")

    lan, body = pick_subtitle(subs, title)
    if not body or len(body.strip()) < 30:
        raise RuntimeError(f"Web 字幕正文过短: {bvid} len={len(body or '')}")
    return lan, body, subs
