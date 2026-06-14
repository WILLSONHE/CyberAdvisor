"""飞书自定义机器人 Webhook（单向推送）。"""
from __future__ import annotations

import json
import urllib.error
import urllib.request


def send_text(webhook_url: str, text: str) -> None:
    payload = {"msg_type": "text", "content": {"text": text[:8000]}}
    _post(webhook_url, payload)


def send_post(webhook_url: str, title: str, lines: list[tuple[str, str]]) -> None:
    """发送富文本 post 消息。每行单独一行，避免两列挤在一起。"""
    content: list[list[dict]] = []
    for tag, text in lines:
        content.append([{"tag": tag, "text": text}])
    payload = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": title[:100],
                    "content": content or [[{"tag": "text", "text": title}]],
                }
            }
        },
    }
    _post(webhook_url, payload)


def _post(webhook_url: str, payload: dict) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"飞书 Webhook HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"飞书 Webhook 网络错误: {e}") from e
    if body.get("code") not in (0, None) and body.get("StatusCode") not in (0, None):
        if body.get("code") != 0:
            raise RuntimeError(f"飞书 Webhook 返回错误: {body}")
