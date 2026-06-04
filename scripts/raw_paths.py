"""Raw 归档目录约定。"""
from __future__ import annotations

import os

from bilibili.env import ROOT

RAW_ROOT = os.path.join(ROOT, "Raw")
RAW_PENDING = os.path.join(RAW_ROOT, "未分析归档")
RAW_ARCHIVED = os.path.join(RAW_ROOT, "已分析归档")

# 兼容旧称（若存在则与未分析归档等价）
RAW_LEGACY_INBOX = os.path.join(RAW_ROOT, "待分析归档")


def ensure_raw_dirs() -> None:
    os.makedirs(RAW_PENDING, exist_ok=True)
    os.makedirs(RAW_ARCHIVED, exist_ok=True)


def pending_dirs() -> list[str]:
    """ing 扫描的待处理目录（未分析归档 + 旧待分析归档）。"""
    dirs = [RAW_PENDING]
    if os.path.isdir(RAW_LEGACY_INBOX) and RAW_LEGACY_INBOX not in dirs:
        dirs.append(RAW_LEGACY_INBOX)
    return dirs


def list_pending_files() -> list[str]:
    out: list[str] = []
    for d in pending_dirs():
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if name.endswith(".md"):
                out.append(os.path.join(d, name))
    return out
