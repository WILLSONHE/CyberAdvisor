"""飞书开放平台 API（Bot 回复）。"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

_TOKEN_CACHE: dict[str, float | str] = {"token": "", "expire_at": 0.0}


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    now = time.time()
    if _TOKEN_CACHE["token"] and now < float(_TOKEN_CACHE["expire_at"]) - 60:
        return str(_TOKEN_CACHE["token"])

    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    payload = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if body.get("code") != 0:
        raise RuntimeError(f"获取 tenant_access_token 失败: {body}")
    token = body["tenant_access_token"]
    expire = int(body.get("expire", 7200))
    _TOKEN_CACHE["token"] = token
    _TOKEN_CACHE["expire_at"] = now + expire
    return token


def reply_text(app_id: str, app_secret: str, message_id: str, text: str) -> None:
    token = get_tenant_access_token(app_id, app_secret)
    url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply"
    content = json.dumps({"text": text[:8000]}, ensure_ascii=False)
    payload = json.dumps({"msg_type": "text", "content": content}, ensure_ascii=False).encode("utf-8")
    _api_post(token, url, payload, action="回复消息")


def send_text_to_chat(app_id: str, app_secret: str, chat_id: str, text: str) -> None:
    """reply 失败时的兜底：按 chat_id 发消息。"""
    token = get_tenant_access_token(app_id, app_secret)
    qs = urllib.parse.urlencode({"receive_id_type": "chat_id"})
    url = f"https://open.feishu.cn/open-apis/im/v1/messages?{qs}"
    content = json.dumps({"text": text[:8000]}, ensure_ascii=False)
    payload = json.dumps(
        {"receive_id": chat_id, "msg_type": "text", "content": content},
        ensure_ascii=False,
    ).encode("utf-8")
    _api_post(token, url, payload, action="发送消息")


def _api_post(token: str, url: str, payload: bytes, *, action: str) -> None:
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"飞书{action} HTTP {e.code}: {detail}") from e
    if body.get("code") != 0:
        raise RuntimeError(f"飞书{action}失败: {body}")
