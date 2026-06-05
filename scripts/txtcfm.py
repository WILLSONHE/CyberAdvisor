#!/usr/bin/env python3
"""
批量审批未审阅文稿（txtcfm = text confirm）。

扫描目录：
  - Raw/未审阅视频文稿/
  - Raw/未分析归档/（及旧称 Raw/待分析归档/）

将 review_status 设为 approved，更新引用行，写入 approved_at。
视频稿审批后移入 Raw/已审阅视频文稿/（类似未分析→已分析归档）。
已 approved / ingested 的跳过。

用法:
  python txtcfm.py
  python txtcfm.py --dry-run
  python txtcfm.py --no-log
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG_PATH = os.path.join(ROOT, "Wiki", "log.md")

sys.path.insert(0, os.path.dirname(__file__))
from raw_paths import (  # noqa: E402
    RAW_PENDING_VIDEO,
    ensure_raw_dirs,
    list_pending_files,
    move_video_to_approved,
)

FM_SPLIT = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
META_REVIEW = re.compile(r"^review_status:\s*(\S+)", re.M)
DONE_STATUSES = frozenset({"approved", "ingested"})


def _set_meta_field(fm: str, key: str, value: str) -> str:
    pat = re.compile(rf"^{re.escape(key)}:.*$", re.M)
    line = f"{key}: {value}"
    if pat.search(fm):
        return pat.sub(line, fm, count=1)
    return fm.rstrip() + "\n" + line


def _get_review_status(fm: str) -> str:
    m = META_REVIEW.search(fm)
    return m.group(1).strip() if m else ""


def _approve_video_body(body: str) -> str:
    return body.replace("B站视频字幕稿（待审阅）", "B站视频字幕稿（已审阅）")


def _prepend_frontmatter(body: str, stamp: str) -> str:
    fm = f"review_status: approved\napproved_at: {stamp}\nsource: manual\n"
    return f"---\n{fm}---\n\n{body.lstrip()}"


def approve_file(path: str, *, dry_run: bool) -> dict:
    result = {"path": path, "action": "skip", "reason": "", "old_status": "", "kind": "raw"}
    text = open(path, encoding="utf-8").read()
    m = FM_SPLIT.match(text)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    if m:
        fm = m.group(1)
        body = text[m.end() :]
        old = _get_review_status(fm)
        result["old_status"] = old or "(none)"
        if old in DONE_STATUSES:
            result["reason"] = "already_done"
            return result
        fm = _set_meta_field(fm, "review_status", "approved")
        fm = _set_meta_field(fm, "approved_at", stamp)
        body = _approve_video_body(body)
        out = f"---\n{fm}\n---\n\n{body.lstrip()}"
    else:
        result["old_status"] = "(none)"
        out = _prepend_frontmatter(text, stamp)
        result["action"] = "approve"

    if m:
        result["action"] = "approve"

    if not dry_run:
        with open(path, "w", encoding="utf-8") as f:
            f.write(out if out.endswith("\n") else out + "\n")
    return result


def collect_files() -> list[tuple[str, str]]:
    """返回 (path, kind) 列表；kind 为 video 或 raw。"""
    items: list[tuple[str, str]] = []
    for p in sorted(glob.glob(os.path.join(RAW_PENDING_VIDEO, "*.md"))):
        items.append((p, "video"))
    for p in list_pending_files():
        items.append((p, "raw"))
    return items


def append_log(approved: list[dict], *, dry_run: bool) -> None:
    if dry_run or not approved:
        return
    today = datetime.now().strftime("%Y-%m-%d")
    video_n = sum(1 for r in approved if r.get("kind") == "video")
    raw_n = len(approved) - video_n
    lines = [
        f"## [{today}] txtcfm × {len(approved)} | 批量审批文稿",
        "",
        "- 操作类型：txtcfm（`scripts/txtcfm.py`）",
        f"- 视频未审阅：{video_n} 篇 → approved，移入 Raw/已审阅视频文稿/",
    ]
    if raw_n:
        lines.append(f"- Raw/未分析归档：{raw_n} 篇 → review_status: approved")
    by_old: dict[str, int] = {}
    for r in approved:
        k = r.get("old_status") or "(none)"
        by_old[k] = by_old.get(k, 0) + 1
    lines.append(f"- 原状态：{', '.join(f'{k} {v}' for k, v in sorted(by_old.items()))}")
    lines.append("")
    block = "\n".join(lines)

    text = open(LOG_PATH, encoding="utf-8").read()
    marker = "\n---\n\n"
    if marker in text:
        head, rest = text.split(marker, 1)
        new_text = head + marker + block + rest
    else:
        new_text = text.rstrip() + "\n\n" + block
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write(new_text)


def main() -> None:
    ap = argparse.ArgumentParser(description="批量审批未审阅文稿（txtcfm）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-log", action="store_true", help="不追加 Wiki/log.md")
    args = ap.parse_args()

    ensure_raw_dirs()
    files = collect_files()
    approved: list[dict] = []
    skipped = 0
    for path, kind in files:
        r = approve_file(path, dry_run=args.dry_run)
        r["kind"] = kind
        name = os.path.basename(path)
        tag = "[DRY] " if args.dry_run else ""
        if r["action"] == "approve":
            if kind == "video":
                if args.dry_run:
                    dest = move_video_to_approved(path, dry_run=True)
                    r["path"] = dest
                else:
                    r["path"] = move_video_to_approved(path)
            approved.append(r)
            dest_note = f" → {os.path.basename(r['path'])}" if kind == "video" else ""
            print(f"{tag}approve  [{kind}] {name}  ({r['old_status']} → approved{dest_note})")
        else:
            skipped += 1
            print(f"{tag}skip    [{kind}] {name}  ({r['reason']})")

    if not args.no_log:
        append_log(approved, dry_run=args.dry_run)

    print(f"\n完成: {len(files)} 扫描 | {len(approved)} 审批 | {skipped} 跳过")


if __name__ == "__main__":
    main()
