"""抖音用户作品列表（aweme/post API，需 Cookie）。"""
from __future__ import annotations

import time
from typing import Any, Iterator

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
POST_API = "https://www.douyin.com/aweme/v1/web/aweme/post/"


def _build_session(*, sec_uid: str, cookie: str) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": DESKTOP_UA,
            "Referer": f"https://www.douyin.com/user/{sec_uid}",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
    )
    for part in cookie.strip().split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            session.cookies.set(k.strip(), v.strip(), domain=".douyin.com")
    return session


class DouyinClient:
    def __init__(self, *, sec_uid: str, cookie: str) -> None:
        if not cookie.strip():
            raise RuntimeError(
                "缺少 DOUYIN_COOKIE。请在 .env 填写 DOUYIN_TTWID / DOUYIN_SESSIONID 等，"
                "或写入 secrets/douyin.cookie。"
            )
        self.sec_uid = sec_uid
        self.session = _build_session(sec_uid=sec_uid, cookie=cookie)
        self._warmup()

    def close(self) -> None:
        self.session.close()

    def _warmup(self) -> None:
        """可选预热；分项 Cookie 已含 ttwid 时失败不影响 API。"""
        for url in (
            "https://www.douyin.com/",
            f"https://www.douyin.com/user/{self.sec_uid}",
        ):
            try:
                self.session.get(url, timeout=20)
            except requests.RequestException:
                continue

    def iter_videos(self, *, page_size: int = 20, sleep_s: float = 0.6) -> Iterator[dict[str, Any]]:
        max_cursor = 0
        seen_cursors: set[int | str] = set()
        while True:
            params = {
                "device_platform": "webapp",
                "aid": "6383",
                "channel": "channel_pc_web",
                "sec_user_id": self.sec_uid,
                "max_cursor": str(max_cursor),
                "count": str(page_size),
                "publish_video_strategy_type": "2",
                "version_code": "190500",
                "version_name": "19.5.0",
            }
            resp = self._request(params)
            data = resp.json()
            if data.get("status_code") not in (0, None):
                raise RuntimeError(
                    f"抖音 API 错误 status_code={data.get('status_code')} "
                    f"msg={data.get('status_msg', '')}"
                )
            aweme_list = data.get("aweme_list") or []
            if not aweme_list:
                break
            for item in aweme_list:
                yield {
                    "aweme_id": str(item.get("aweme_id") or ""),
                    "title": (item.get("desc") or "").strip(),
                    "create_time": int(item.get("create_time") or 0),
                }
            if not data.get("has_more"):
                break
            next_cursor = data.get("max_cursor", 0)
            if next_cursor in seen_cursors:
                break
            seen_cursors.add(next_cursor)
            max_cursor = next_cursor
            time.sleep(sleep_s)

    def _request(self, params: dict[str, str]) -> requests.Response:
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                resp = self.session.get(POST_API, params=params, timeout=30)
                if not resp.content:
                    raise RuntimeError(
                        "抖音作品列表 API 返回空响应。Cookie 可能过期，请更新 "
                        "DOUYIN_TTWID / DOUYIN_SESSIONID 或 DOUYIN_COOKIE。"
                    )
                return resp
            except requests.SSLError as e:
                last_err = e
                time.sleep(1.0 + attempt)
            except requests.ConnectionError as e:
                last_err = e
                time.sleep(1.0 + attempt)
        hint = (
            "连接 douyin.com 时 SSL/网络失败（非 Cookie 格式问题）。"
            "请检查网络/代理/VPN，稍后重试；或换网络再跑 douyin_cookie_check.py。"
        )
        raise RuntimeError(hint) from last_err
