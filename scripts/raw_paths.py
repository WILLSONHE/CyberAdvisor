"""Raw 归档目录约定。"""
from __future__ import annotations

import os
import re
import shutil
from datetime import datetime

from bilibili.env import ROOT

RAW_ROOT = os.path.join(ROOT, "Raw")
RAW_PENDING = os.path.join(RAW_ROOT, "未分析归档")
RAW_ARCHIVED = os.path.join(RAW_ROOT, "已分析归档")
RAW_PENDING_VIDEO = os.path.join(RAW_ROOT, "未审阅视频文稿")
RAW_APPROVED_VIDEO = os.path.join(RAW_ROOT, "已审阅视频文稿")
RAW_PENDING_MATERIALS = os.path.join(RAW_ROOT, "未分析其他材料")
RAW_ARCHIVED_MATERIALS = os.path.join(RAW_ROOT, "已分析其他材料")
WIKI_MATERIALS = os.path.join(ROOT, "Wiki", "其他材料")

# 其他材料 ingest 支持的扩展名（小写）
MATERIAL_EXTENSIONS = frozenset({".md", ".txt", ".pdf", ".pptx", ".docx"})

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
    os.makedirs(RAW_PENDING_MATERIALS, exist_ok=True)
    os.makedirs(RAW_ARCHIVED_MATERIALS, exist_ok=True)
    os.makedirs(WIKI_MATERIALS, exist_ok=True)
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


_FM_SPLIT = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
_META_TYPE = re.compile(r"^type:\s*(\S+)", re.M)
_BVID_IN_NAME = re.compile(r"_BV[\w]+\_", re.I)


def is_video_transcript(path: str) -> bool:
    """是否为 B 站视频字幕稿（ing 后留已审阅目录，不进已分析归档）。"""
    name = os.path.basename(path)
    if _BVID_IN_NAME.search(name):
        return True
    norm = os.path.normpath(path)
    if RAW_APPROVED_VIDEO in norm or RAW_PENDING_VIDEO in norm:
        return True
    try:
        text = open(path, encoding="utf-8").read(4096)
    except OSError:
        return False
    m = _FM_SPLIT.match(text)
    if not m:
        return False
    fm = m.group(1)
    tm = _META_TYPE.search(fm)
    return bool(tm and tm.group(1) == "video_transcript")


def _set_meta_field(fm: str, key: str, value: str) -> str:
    pat = re.compile(rf"^{re.escape(key)}:.*$", re.M)
    line = f"{key}: {value}"
    if pat.search(fm):
        return pat.sub(line, fm, count=1)
    return fm.rstrip() + "\n" + line


def mark_video_ingested(src: str, *, dry_run: bool = False) -> str:
    """视频稿 ingest 后：review_status→ingested，文件留在已审阅视频文稿。"""
    ensure_raw_dirs()
    if not os.path.isfile(src):
        raise FileNotFoundError(src)
    if not is_video_transcript(src):
        raise ValueError(f"not a video transcript: {src}")

    text = open(src, encoding="utf-8").read()
    m = _FM_SPLIT.match(text)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    if m:
        fm = _set_meta_field(m.group(1), "review_status", "ingested")
        fm = _set_meta_field(fm, "ingested_at", stamp)
        body = text[m.end() :]
        out = f"---\n{fm}\n---\n\n{body.lstrip()}"
    else:
        out = text

    approved = os.path.normpath(RAW_APPROVED_VIDEO)
    src_norm = os.path.normpath(os.path.abspath(src))
    approved_prefix = approved + os.sep
    if not src_norm.startswith(approved_prefix):
        dest = _unique_path(RAW_APPROVED_VIDEO, os.path.basename(src))
        if dry_run:
            return dest
        with open(src, "w", encoding="utf-8") as f:
            f.write(out if out.endswith("\n") else out + "\n")
        shutil.move(src, dest)
        return dest

    if dry_run:
        return src
    with open(src, "w", encoding="utf-8") as f:
        f.write(out if out.endswith("\n") else out + "\n")
    return src


def restore_videos_from_archived(*, dry_run: bool = False) -> list[str]:
    """将误放入已分析归档的视频稿移回已审阅视频文稿。"""
    ensure_raw_dirs()
    moved: list[str] = []
    if not os.path.isdir(RAW_ARCHIVED):
        return moved
    for name in sorted(os.listdir(RAW_ARCHIVED)):
        if not name.endswith(".md"):
            continue
        src = os.path.join(RAW_ARCHIVED, name)
        if not is_video_transcript(src):
            continue
        dest = _unique_path(RAW_APPROVED_VIDEO, name)
        if dry_run:
            print(f"  [DRY] {name} -> 已审阅视频文稿/")
            moved.append(dest)
            continue
        shutil.move(src, dest)
        print(f"  [OK] restored {name}")
        moved.append(dest)
    return moved


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


def list_pending_material_files() -> list[str]:
    """ing 扫描的其他材料（pdf/pptx/docx/txt/md）。"""
    ensure_raw_dirs()
    out: list[str] = []
    if not os.path.isdir(RAW_PENDING_MATERIALS):
        return out
    for name in sorted(os.listdir(RAW_PENDING_MATERIALS)):
        if name.startswith("."):
            continue
        path = os.path.join(RAW_PENDING_MATERIALS, name)
        if not os.path.isfile(path):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext in MATERIAL_EXTENSIONS:
            out.append(path)
    return out
