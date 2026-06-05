"""Raw 归档目录约定。"""
from __future__ import annotations

import os
import shutil

from bilibili.env import ROOT

RAW_ROOT = os.path.join(ROOT, "Raw")
RAW_PENDING = os.path.join(RAW_ROOT, "未分析归档")
RAW_ARCHIVED = os.path.join(RAW_ROOT, "已分析归档")
RAW_PENDING_VIDEO = os.path.join(RAW_ROOT, "未审阅视频文稿")
RAW_APPROVED_VIDEO = os.path.join(RAW_ROOT, "已审阅视频文稿")

# 兼容旧路径
LEGACY_WIKI_PENDING_VIDEO = os.path.join(ROOT, "Wiki", "待审阅视频文稿")
LEGACY_RAW_PENDING_VIDEO = os.path.join(RAW_ROOT, "待审阅视频文稿")
# 旧常量名（Wiki 待审阅目录，迁移脚本用）
LEGACY_PENDING_VIDEO = LEGACY_WIKI_PENDING_VIDEO

# 兼容旧称（若存在则与未分析归档等价）
RAW_LEGACY_INBOX = os.path.join(RAW_ROOT, "待分析归档")


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


def _migrate_legacy_video_inbox(legacy_dir: str) -> None:
    if not os.path.isdir(legacy_dir) or os.path.normpath(legacy_dir) == os.path.normpath(RAW_PENDING_VIDEO):
        return
    os.makedirs(RAW_PENDING_VIDEO, exist_ok=True)
    for name in os.listdir(legacy_dir):
        src = os.path.join(legacy_dir, name)
        if not os.path.isfile(src):
            continue
        shutil.move(src, _unique_path(RAW_PENDING_VIDEO, name))
    try:
        os.rmdir(legacy_dir)
    except OSError:
        pass


def ensure_raw_dirs() -> None:
    os.makedirs(RAW_PENDING, exist_ok=True)
    os.makedirs(RAW_ARCHIVED, exist_ok=True)
    os.makedirs(RAW_PENDING_VIDEO, exist_ok=True)
    os.makedirs(RAW_APPROVED_VIDEO, exist_ok=True)
    for leg in (LEGACY_WIKI_PENDING_VIDEO, LEGACY_RAW_PENDING_VIDEO):
        _migrate_legacy_video_inbox(leg)


def move_video_to_approved(src: str, *, dry_run: bool = False) -> str:
    """txtcfm 审批后将视频稿移入已审阅视频文稿。"""
    ensure_raw_dirs()
    if not os.path.isfile(src):
        raise FileNotFoundError(src)
    dest = _unique_path(RAW_APPROVED_VIDEO, os.path.basename(src))
    if dry_run:
        return dest
    shutil.move(src, dest)
    return dest


def pending_dirs() -> list[str]:
    """ing 扫描的手动 Raw 待处理目录（未分析归档 + 旧待分析归档）。"""
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
