#!/usr/bin/env python3
"""
视频文字稿 rw（rewrite）：格式化 + ASR 术语校正 + 可选重拉 B 站字幕。

目标目录：
  - Raw/未审阅视频文稿/  （rw 后用户 txtcfm 审批 → 已审阅视频文稿，再 ing）
  - Raw/已分析归档/视频*.md、周复盘*.md

用法:
  python rw_video.py                    # 处理全部
  python rw_video.py --pending-only     # 仅待审阅
  python rw_video.py --refetch          # 有 bvid 时尝试重拉字幕
  python rw_video.py --punctuate       # 仅补标点+分段（不重拉字幕、不改 ASR）
  python rw_video.py --dry-run
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys
import time
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from raw_paths import RAW_PENDING_VIDEO  # noqa: E402

PENDING_DIR = RAW_PENDING_VIDEO
ARCHIVED_DIR = os.path.join(ROOT, "Raw", "已分析归档")

sys.path.insert(0, os.path.dirname(__file__))

from bilibili.asr_fixes import apply_asr_fixes, looks_like_mismatch  # noqa: E402
from bilibili.client import BiliClient  # noqa: E402
from bilibili.env import BiliConfig  # noqa: E402
from bilibili.rw_format import format_transcript, needs_punctuation, re_punctuate  # noqa: E402
from bilibili.transcript import pick_subtitle, score_subtitle  # noqa: E402

META_BVID = re.compile(r"^bvid:\s*(\S+)", re.M)
META_TITLE = re.compile(r"^title:\s*(.+)$", re.M)
FM_SPLIT = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def _parse_md(path: str) -> tuple[str, str, str]:
    """返回 (frontmatter_raw, body, full_text)。"""
    text = open(path, encoding="utf-8").read()
    m = FM_SPLIT.match(text)
    if m:
        return m.group(1), text[m.end() :], text
    return "", text, text


def _set_meta_field(fm: str, key: str, value: str) -> str:
    pat = re.compile(rf"^{re.escape(key)}:.*$", re.M)
    line = f"{key}: {value}"
    if pat.search(fm):
        return pat.sub(line, fm, count=1)
    return fm.rstrip() + "\n" + line


def _extract_body_content(body: str) -> tuple[str, str, str]:
    """分离标题行、引用行、正文。"""
    lines = body.splitlines()
    prefix: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("# ") or (line.startswith(">") and i < 5):
            prefix.append(line)
            i += 1
            continue
        if line.strip() == "" and prefix:
            prefix.append(line)
            i += 1
            continue
        break
    prefix_str = "\n".join(prefix).rstrip()
    content = "\n".join(lines[i:]).strip()
    return prefix_str, content, body


def _refetch(bvid: str, client: BiliClient, title: str = "") -> tuple[str, str, int]:
    view = client.video_view(bvid)
    cid = view.get("cid")
    if not cid:
        return "", "", -999
    subs = client.video_subtitles(bvid, cid)
    lan, body = pick_subtitle(subs, title)
    return lan, body, score_subtitle(body, title)


def _append_rw_note(body: str, note: str) -> str:
    if "rw_at:" in body or "## 校对说明" in body:
        # 更新 rw_at 行
        if re.search(r"^rw_at:", body, re.M):
            return re.sub(r"^rw_at:.*$", f"rw_at: {note}", body, flags=re.M)
        return body
    stamp = datetime.now().strftime("%Y-%m-%d")
    block = f"\n\n---\n\n## 校对说明\n\n- rw_at: {stamp}\n- {note}\n"
    return body.rstrip() + block


def process_file(
    path: str,
    *,
    client: BiliClient | None,
    refetch: bool,
    punctuate_only: bool,
    dry_run: bool,
    is_pending: bool,
) -> dict:
    result = {"path": path, "action": "skip", "reason": ""}
    fm, body, _ = _parse_md(path)
    bvid_m = META_BVID.search(fm)
    title_m = META_TITLE.search(fm)
    bvid = bvid_m.group(1) if bvid_m else ""
    title = title_m.group(1).strip() if title_m else os.path.basename(path)

    prefix, content, _ = _extract_body_content(body)
    already_structured = bool(re.search(r"^## ", content, re.M)) and "校对说明" in body
    new_content = content

    old_score = score_subtitle(content, title)

    # 待审阅：可重拉字幕（仅当新轨评分更高）
    if is_pending and refetch and not punctuate_only and bvid and client:
        try:
            lan, fetched, new_score = _refetch(bvid, client, title)
            if fetched and new_score > old_score + 2:
                new_content = format_transcript(fetched)
                fm = _set_meta_field(fm, "subtitle_lang", lan)
                result["action"] = "refetch"
            elif fetched and new_score <= old_score:
                result["reason"] = "refetch_worse_kept_local"
            elif not fetched:
                result["reason"] = "no_subtitle"
            elif looks_like_mismatch(fetched, title):
                result["reason"] = "subtitle_mismatch"
            time.sleep(0.4)
        except Exception as e:
            result["reason"] = f"refetch_error:{e}"

    # 标点 + 分段（待审阅默认；已归档仅对无结构长文）
    should_format = is_pending or (not already_structured)
    if should_format and new_content and not re.search(r"^## ", new_content, re.M):
        force_punct = is_pending and (needs_punctuation(new_content) or punctuate_only)
        if len(new_content) > 80 and (force_punct or punctuate_only or is_pending):
            if punctuate_only:
                formatted = re_punctuate(new_content)
            else:
                formatted = format_transcript(new_content, force_punctuate=True)
            if formatted:
                new_content = formatted
                result["action"] = "punctuate" if punctuate_only else "format"

    # ASR 校正（全文；--punctuate 模式跳过）
    if not punctuate_only:
        fixed, changes = apply_asr_fixes(new_content)
        if changes:
            new_content = fixed
            if result["action"] == "skip":
                result["action"] = "asr_fix"
    else:
        changes = []

    if new_content == content and result["action"] == "skip":
        result["reason"] = "unchanged"
        return result

    # 状态
    if is_pending:
        status = "rewritten"
        if looks_like_mismatch(new_content, title) or score_subtitle(new_content, title) < 8:
            status = "subtitle_mismatch"
        elif re.fullmatch(r"(音乐[♪\s]*)+", new_content.strip()) or len(new_content.strip()) < 20:
            status = "extraction_failed"
        fm = _set_meta_field(fm, "review_status", status)
        fm = _set_meta_field(fm, "rw_at", datetime.now().strftime("%Y-%m-%d %H:%M"))

    new_body = prefix + "\n\n" + new_content if prefix else new_content
    if not is_pending and not already_structured:
        new_body = _append_rw_note(new_body, "脚本 rw_video.py 自动格式化 + ASR 术语校正")
    elif not is_pending and changes:
        new_body = _append_rw_note(
            new_body,
            f"ASR 术语校正：{'; '.join(changes[:8])}" + ("…" if len(changes) > 8 else ""),
        )

    out = f"---\n{fm}\n---\n\n{new_body}\n"
    if not dry_run:
        with open(path, "w", encoding="utf-8") as f:
            f.write(out)
    result["changes"] = len(changes)
    if result["action"] == "skip":
        result["action"] = "update"
    return result


def collect_files(pending_only: bool, archived_only: bool) -> list[tuple[str, bool]]:
    items: list[tuple[str, bool]] = []
    if not archived_only:
        for p in sorted(glob.glob(os.path.join(PENDING_DIR, "*.md"))):
            items.append((p, True))
    if not pending_only:
        for pat in ("视频*.md", "周复盘*.md"):
            for p in sorted(glob.glob(os.path.join(ARCHIVED_DIR, pat))):
                items.append((p, False))
    return items


def main() -> None:
    ap = argparse.ArgumentParser(description="视频文字稿 rw")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pending-only", action="store_true")
    ap.add_argument("--archived-only", action="store_true")
    ap.add_argument("--refetch", action="store_true", help="对待审阅文件重拉 B 站字幕")
    ap.add_argument(
        "--punctuate",
        action="store_true",
        help="仅补标点与分段（默认对待审阅也会执行）",
    )
    args = ap.parse_args()

    files = collect_files(args.pending_only, args.archived_only)
    client: BiliClient | None = None
    if args.refetch:
        client = BiliClient(BiliConfig.load())

    stats = {"refetch": 0, "format": 0, "punctuate": 0, "asr_fix": 0, "update": 0, "skip": 0, "mismatch": 0}
    try:
        for path, is_pending in files:
            r = process_file(
                path,
                client=client,
                refetch=args.refetch and is_pending,
                punctuate_only=args.punctuate,
                dry_run=args.dry_run,
                is_pending=is_pending,
            )
            act = r.get("action", "skip")
            stats[act] = stats.get(act, 0) + 1
            if r.get("reason") == "subtitle_mismatch":
                stats["mismatch"] += 1
            name = os.path.basename(path)
            tag = "[DRY] " if args.dry_run else ""
            print(f"{tag}{act:8} {name} {r.get('reason','')} changes={r.get('changes',0)}")
    finally:
        if client:
            client.close()

    print(f"\n完成: {len(files)} 文件 | {stats}")


if __name__ == "__main__":
    main()
