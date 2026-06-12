"""抖音未审阅文稿文件名（对齐 bilibili pending 命名）。"""
from __future__ import annotations

from bilibili.naming import pending_video_filename


def pending_douyin_filename(title: str, aweme_id: str, pub_ts: int | None = None) -> str:
    return pending_video_filename(title, aweme_id, pub_ts)
