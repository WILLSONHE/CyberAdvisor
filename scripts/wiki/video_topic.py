"""已审阅视频 → Wiki/视频专题 流水线辅助。"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from typing import Any

from bilibili.env import ROOT

from raw_paths import (
    RAW_APPROVED_VIDEO,
    _FM_SPLIT,
    _set_meta_field,
    ensure_raw_dirs,
    is_video_transcript,
)

WIKI = os.path.join(ROOT, "Wiki")
WIKI_VIDEO_TOPIC = os.path.join(WIKI, "视频专题")
WIKI_VIDEO_TOPIC_INDEX = os.path.join(WIKI_VIDEO_TOPIC, "视频专题索引.md")

VIDEO_TOPIC_CATEGORIES = ("复盘", "宏观", "产业", "方法论")

# 分类启发式（先匹配方法论/宏观/产业，其余默认复盘）
_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "方法论",
        (
            "K线",
            "k线",
            "技术分析",
            "设置盘面",
            "通达信",
            "充电资讯",
            "信息差",
            "复盘SOP",
            "四屏",
        ),
    ),
    (
        "宏观",
        (
            "宏观",
            "再通胀",
            "金融大棋",
            "2028",
            "资本狂潮",
            "房地产",
            "港股",
            "分化时代",
            "美债",
            "通胀",
            "蒙代尔",
            "K型",
            "K 型",
        ),
    ),
        (
            "产业",
            (
                "产业链梳理",
                "高景气",
                "韬定律",
                "HBM",
                "BOM",
                "机柜",
            ),
        ),
)

_META = {
    "bvid": re.compile(r"^bvid:\s*(.+)$", re.M),
    "title": re.compile(r"^title:\s*(.+)$", re.M),
    "review_status": re.compile(r"^review_status:\s*(\S+)", re.M),
    "wiki_topic_path": re.compile(r"^wiki_topic_path:\s*(.+)$", re.M),
    "pub_time": re.compile(r"^pub_time:\s*(.+)$", re.M),
}

_RAW_NAME = re.compile(
    r"^(\d{2}-\d{2}-\d{2})_BV[\w]+_(.+)\.md$", re.I
)


def _read_fm(path: str) -> tuple[dict[str, str], str]:
    text = open(path, encoding="utf-8").read()
    m = _FM_SPLIT.match(text)
    if not m:
        return {}, text
    fm_text = m.group(1)
    fm: dict[str, str] = {}
    for key, pat in _META.items():
        mm = pat.search(fm_text)
        if mm:
            fm[key] = mm.group(1).strip().strip('"')
    return fm, text


def _sanitize_slug(text: str, *, max_len: int = 40) -> str:
    s = text.strip().strip('"').strip("'")
    for ch in "?？!！。，,、；;：:\"'（）()【】[]《》<> ":
        s = s.replace(ch, "")
    s = s.replace("（", "").replace("）", "")
    s = re.sub(r"\s+", "", s)
    if len(s) > max_len:
        s = s[:max_len]
    return s or "未命名"


def wiki_slug_from_raw_basename(name: str, *, title: str | None = None) -> str:
    """26-05-14_BV1xxx_倒车接人.md → 视频26-05-14-倒车接人"""
    m = _RAW_NAME.match(name)
    if m:
        date_part, raw_title = m.group(1), m.group(2)
        slug_title = _sanitize_slug(title or raw_title)
        return f"视频{date_part}-{slug_title}"
    stem, _ = os.path.splitext(name)
    return f"视频-{_sanitize_slug(stem)}"


def classify_video_category(
    *,
    title: str = "",
    filename: str = "",
    body: str = "",
) -> str:
    hay = f"{title}\n{filename}\n{body[:4000]}"
    for category, keywords in _CATEGORY_RULES:
        if any(k in hay for k in keywords):
            return category
    if "周复盘" in hay or "复盘" in filename:
        return "复盘"
    return "复盘"


def suggest_wiki_topic_relpath(raw_path: str) -> str:
    """建议写入的 Wiki 相对路径（相对项目根）。"""
    ensure_raw_dirs()
    name = os.path.basename(raw_path)
    fm, text = _read_fm(raw_path)
    title = fm.get("title", "")
    body = _FM_SPLIT.sub("", text, count=1) if _FM_SPLIT.match(text) else text
    category = classify_video_category(title=title, filename=name, body=body)
    slug = wiki_slug_from_raw_basename(name, title=title)
    return f"Wiki/视频专题/{category}/{slug}.md"


def list_approved_video_files() -> list[str]:
    """已审阅视频文稿目录下全部 .md（不含 .gitkeep）。"""
    ensure_raw_dirs()
    if not os.path.isdir(RAW_APPROVED_VIDEO):
        return []
    out: list[str] = []
    for name in sorted(os.listdir(RAW_APPROVED_VIDEO)):
        if name.endswith(".md"):
            out.append(os.path.join(RAW_APPROVED_VIDEO, name))
    return out


def _video_ing_tasks(fm: dict[str, str]) -> list[str]:
    status = fm.get("review_status", "")
    has_topic = bool(fm.get("wiki_topic_path"))
    tasks: list[str] = []
    if status == "approved":
        tasks.append("daily_wiki")
        if not has_topic:
            tasks.append("video_topic")
    elif status == "ingested" and not has_topic:
        tasks.append("video_topic")
    return tasks


def list_video_ing_pending() -> list[dict[str, Any]]:
    """ing 应处理的视频稿队列（日更 +/或 视频专题）。"""
    pending: list[dict[str, Any]] = []
    for path in list_approved_video_files():
        if not is_video_transcript(path):
            continue
        fm, _ = _read_fm(path)
        tasks = _video_ing_tasks(fm)
        if not tasks:
            continue
        pending.append(
            {
                "path": path,
                "relpath": os.path.relpath(path, ROOT).replace("\\", "/"),
                "bvid": fm.get("bvid", ""),
                "title": fm.get("title", ""),
                "review_status": fm.get("review_status", ""),
                "wiki_topic_path": fm.get("wiki_topic_path", ""),
                "tasks": tasks,
                "suggested_wiki_topic": suggest_wiki_topic_relpath(path),
                "suggested_category": classify_video_category(
                    title=fm.get("title", ""),
                    filename=os.path.basename(path),
                    body=open(path, encoding="utf-8").read()[:4000],
                ),
            }
        )
    return pending


def mark_video_wiki_topic(
    raw_path: str,
    wiki_rel_path: str,
    *,
    dry_run: bool = False,
) -> str:
    """ing 完成视频专题页后，回写 raw frontmatter。"""
    ensure_raw_dirs()
    if not os.path.isfile(raw_path):
        raise FileNotFoundError(raw_path)
    if not is_video_transcript(raw_path):
        raise ValueError(f"not a video transcript: {raw_path}")

    wiki_rel = wiki_rel_path.replace("\\", "/").lstrip("/")
    if not wiki_rel.startswith("Wiki/视频专题/"):
        raise ValueError(f"wiki_topic_path must be under Wiki/视频专题/: {wiki_rel}")

    text = open(raw_path, encoding="utf-8").read()
    m = _FM_SPLIT.match(text)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    if m:
        fm = _set_meta_field(m.group(1), "wiki_topic_path", wiki_rel)
        fm = _set_meta_field(fm, "wiki_topic_at", stamp)
        body = text[m.end() :]
        out = f"---\n{fm}\n---\n\n{body.lstrip()}"
    else:
        raise ValueError(f"missing frontmatter: {raw_path}")

    if dry_run:
        return raw_path
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(out if out.endswith("\n") else out + "\n")
    return raw_path


def find_wiki_topic_by_bvid(bvid: str) -> str | None:
    """在 Wiki/视频专题 中按 bvid 查找已有专题页（相对路径）。"""
    if not bvid or not os.path.isdir(WIKI_VIDEO_TOPIC):
        return None
    pat = re.compile(rf"^bvid:\s*{re.escape(bvid)}\s*$", re.M)
    for dirpath, _, names in os.walk(WIKI_VIDEO_TOPIC):
        for name in names:
            if not name.endswith(".md") or name == "视频专题索引.md":
                continue
            path = os.path.join(dirpath, name)
            try:
                head = open(path, encoding="utf-8").read(2048)
            except OSError:
                continue
            if pat.search(head):
                return os.path.relpath(path, ROOT).replace("\\", "/")
    return None


def backfill_wiki_topic_meta(*, dry_run: bool = False) -> list[tuple[str, str]]:
    """从已有 Wiki/视频专题 页反填 raw 的 wiki_topic_path（一次性/补漏）。"""
    updated: list[tuple[str, str]] = []
    for raw in list_approved_video_files():
        fm, _ = _read_fm(raw)
        if fm.get("wiki_topic_path"):
            continue
        bvid = fm.get("bvid", "")
        wiki_rel = find_wiki_topic_by_bvid(bvid) if bvid else None
        if not wiki_rel:
            continue
        if dry_run:
            updated.append((raw, wiki_rel))
            continue
        mark_video_wiki_topic(raw, wiki_rel)
        updated.append((raw, wiki_rel))
    return updated


# Agent 写页模板（SKILL / ing_pending 输出引用）
VIDEO_TOPIC_PAGE_SECTIONS = """
## 核心观点
## 指数/盘面判断（复盘类）或 ## 核心框架（宏观类）或 ## 产业链框架（产业类）或 ## 工具与 setup（方法论类）
## 板块与标的（如适用）
## 操作纪律（如适用）
## 链接
""".strip()


def _cli_mark(args: argparse.Namespace) -> int:
    mark_video_wiki_topic(args.raw, args.wiki, dry_run=args.dry_run)
    print(f"  [OK] wiki_topic_path → {args.wiki}")
    return 0


def _cli_pending(_: argparse.Namespace) -> int:
    for item in list_video_ing_pending():
        print(json.dumps(item, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    import json

    parser = argparse.ArgumentParser(description="视频专题 Wiki 辅助")
    sub = parser.add_subparsers(dest="cmd")

    p_mark = sub.add_parser("mark", help="ing 完成后回写 raw wiki_topic_path")
    p_mark.add_argument("--raw", required=True, help="Raw 已审阅视频文稿路径")
    p_mark.add_argument("--wiki", required=True, help="Wiki 相对路径，如 Wiki/视频专题/复盘/...")
    p_mark.add_argument("--dry-run", action="store_true")
    p_mark.set_defaults(func=_cli_mark)

    p_bf = sub.add_parser("backfill-meta", help="从已有专题页反填 raw")
    p_bf.add_argument("--dry-run", action="store_true")

    def _bf(args: argparse.Namespace) -> int:
        for raw, wiki in backfill_wiki_topic_meta(dry_run=args.dry_run):
            print(f"  {'DRY' if args.dry_run else 'OK'}: {os.path.basename(raw)} → {wiki}")
        return 0

    p_bf.set_defaults(func=_bf)

    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    _scripts = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _root = os.path.dirname(_scripts)
    for p in (_root, _scripts):
        if p not in sys.path:
            sys.path.insert(0, p)
    raise SystemExit(main())
