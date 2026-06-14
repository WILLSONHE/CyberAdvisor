"""B 站 API 客户端（含 WBI 签名）。"""
from __future__ import annotations

import hashlib
import time
import urllib.parse
from functools import reduce
from typing import Any

import requests

from .env import BiliConfig

WBI_MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52,
]


def _mixin_key(orig: str) -> str:
    return reduce(lambda s, i: s + orig[i], WBI_MIXIN_KEY_ENC_TAB, "")[:32]


def _enc_wbi(params: dict[str, Any], img_key: str, sub_key: str) -> dict[str, Any]:
    params = dict(params)
    params["wts"] = round(time.time())
    params = dict(sorted(params.items()))
    params = {
        k: "".join(ch for ch in str(v) if ch not in "!'()*")
        for k, v in params.items()
    }
    query = urllib.parse.urlencode(params)
    params["w_rid"] = hashlib.md5((query + _mixin_key(img_key + sub_key)).encode()).hexdigest()
    return params


class BiliClient:
    def __init__(self, config: BiliConfig):
        self.config = config
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.bilibili.com/",
            "Cookie": config.cookie_header(),
        })
        self._img_key: str | None = None
        self._sub_key: str | None = None

    def close(self) -> None:
        self.session.close()

    def _refresh_wbi_keys(self) -> None:
        resp = self.session.get("https://api.bilibili.com/x/web-interface/nav", timeout=20)
        resp.raise_for_status()
        payload = resp.json()
        # code=-101 时 data.wbi_img 仍可用（访客 nav）
        inner = (payload.get("data") or {}).get("wbi_img") or payload.get("wbi_img") or {}
        img_url = inner.get("img_url", "")
        sub_url = inner.get("sub_url", "")
        if not img_url or not sub_url:
            raise RuntimeError(
                f"无法获取 WBI keys: nav code={payload.get('code')} msg={payload.get('message')}"
            )
        self._img_key = img_url.rsplit("/", 1)[-1].split(".")[0]
        self._sub_key = sub_url.rsplit("/", 1)[-1].split(".")[0]

    def _wbi_get(self, url: str, params: dict[str, Any]) -> dict:
        if not self._img_key or not self._sub_key:
            self._refresh_wbi_keys()
        signed = _enc_wbi(params, self._img_key, self._sub_key)
        return self.get_json(url, params=signed)

    def get_json(
        self,
        url: str,
        params: dict | None = None,
        timeout: int = 20,
        retries: int = 6,
    ) -> dict:
        last_err = None
        for attempt in range(retries):
            try:
                resp = self.session.get(url, params=params, timeout=timeout)
                resp.raise_for_status()
                data = resp.json()
            except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as exc:
                last_err = exc
                if attempt + 1 < retries:
                    time.sleep(min(60.0, 4.0 * (2 ** attempt)))
                    continue
                raise
            code = data.get("code", 0)
            if code in (0,):
                return data.get("data") or data
            if code in (-352, -412) and attempt + 1 < retries:
                time.sleep(min(60.0, 4.0 * (2 ** attempt)))
                continue
            last_err = RuntimeError(f"API {url} code={code} msg={data.get('message')}")
        raise last_err or RuntimeError(f"API {url} failed")

    def iter_videos(self, page_size: int = 30):
        """空间投稿视频（含充电）。"""
        pn = 1
        while True:
            data = self._wbi_get(
                "https://api.bilibili.com/x/space/wbi/arc/search",
                {
                    "mid": self.config.uid,
                    "ps": page_size,
                    "pn": pn,
                    "order": "pubdate",
                    "index": 0,
                    "order_avoided": "true",
                },
            )
            vlist = (data.get("list") or {}).get("vlist") or []
            if not vlist:
                break
            yield from vlist
            if len(vlist) < page_size:
                break
            pn += 1
            time.sleep(0.4)

    def iter_dynamics(self):
        """空间动态（图文/opus）。前几页可能为空，需按 offset 翻页。"""
        offset = ""
        empty_pages = 0
        while True:
            params: dict[str, Any] = {
                "host_mid": self.config.uid,
                "timezone_offset": -480,
                "features": "itemOpusStyle,forwardScrollSplit",
            }
            if offset:
                params["offset"] = offset
            data = self.get_json(
                "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space",
                params=params,
            )
            items = data.get("items") or []
            if items:
                empty_pages = 0
                yield from items
            else:
                empty_pages += 1

            offset = data.get("offset") or ""
            has_more = data.get("has_more")
            if not has_more or not offset:
                break
            if empty_pages >= 30:
                break
            time.sleep(0.7)

    def dynamic_detail(self, dynamic_id: str) -> dict:
        return self.get_json(
            "https://api.bilibili.com/x/polymer/web-dynamic/v1/detail",
            params={
                "id": dynamic_id,
                "features": "itemOpusStyle,forwardScrollSplit",
                "timezone_offset": -480,
                "web_location": "333.1365",
            },
        )

    def iter_articles(self, page_size: int = 30):
        pn = 1
        while True:
            data = self.get_json(
                "https://api.bilibili.com/x/space/article",
                params={"mid": self.config.uid, "pn": pn, "ps": page_size, "sort": "publish_time"},
            )
            articles = data.get("articles") or []
            if not articles:
                break
            yield from articles
            if len(articles) < page_size:
                break
            pn += 1
            time.sleep(0.4)

    def article_detail(self, cvid: int, *, from_source: str = "") -> dict:
        params: dict[str, Any] = {"id": cvid}
        if from_source:
            params["from"] = from_source
        return self.get_json(
            "https://api.bilibili.com/x/article/view",
            params=params,
        )

    def iter_opus_feed(self):
        """充电/专栏 opus 列表（含公开专栏 API 未列出的充电文）。"""
        offset = ""
        while True:
            params: dict[str, Any] = {
                "host_mid": self.config.uid,
                "timezone_offset": -480,
            }
            if offset:
                params["offset"] = offset
            data = self.get_json(
                "https://api.bilibili.com/x/polymer/web-dynamic/v1/opus/feed/space",
                params=params,
            )
            items = data.get("items") or []
            if items:
                yield from items
            offset = data.get("offset") or ""
            if not data.get("has_more") or not offset:
                break
            time.sleep(0.5)

    def opus_detail(self, opus_id: str) -> dict:
        return self.get_json(
            "https://api.bilibili.com/x/polymer/web-dynamic/v1/opus/detail",
            params={"id": opus_id, "timezone_offset": -480},
        )

    def video_view(self, bvid: str) -> dict:
        return self.get_json(
            "https://api.bilibili.com/x/web-interface/view",
            params={"bvid": bvid},
        )

    def video_subtitles(self, bvid: str, cid: int) -> list[dict]:
        """拉取字幕轨；充电/抢先看视频优先 WBI player（v2 常返回错误 ai 轨）。"""
        data = self._player_subtitle_payload(bvid, cid)
        subs = ((data.get("subtitle") or {}).get("subtitles")) or []
        result = []
        for sub in subs:
            url = sub.get("subtitle_url") or ""
            if not url:
                continue
            if url.startswith("//"):
                url = "https:" + url
            elif url.startswith("/"):
                url = "https://api.bilibili.com" + url
            body = self.session.get(url, timeout=20).json().get("body") or []
            text = "".join(item.get("content", "") for item in body)
            result.append({
                "lan": sub.get("lan", ""),
                "lan_doc": sub.get("lan_doc", ""),
                "ai": str(sub.get("lan", "")).startswith("ai-"),
                "text": text,
            })
        result.sort(key=lambda x: (x["ai"], x["lan"] != "zh-CN"))
        return result

    def _player_subtitle_payload(self, bvid: str, cid: int) -> dict:
        params = {"bvid": bvid, "cid": cid}
        try:
            return self._wbi_get("https://api.bilibili.com/x/player/wbi/v2", params)
        except Exception:
            pass
        return self.get_json("https://api.bilibili.com/x/player/v2", params=params)
