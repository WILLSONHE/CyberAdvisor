"""本机 Wiki 目录树与文件查找（飞书 Bot）。"""
from __future__ import annotations

import os
from pathlib import Path

from bilibili.env import ROOT

WIKI_ROOT = os.path.join(ROOT, "Wiki")

SKIP_FILES = frozenset({"feishu_debug.log"})

# 策略文件树：只显示目录，不展开子文件
COLLAPSE_DIRS: dict[str, str] = {
    "每日复盘": "文件列表已省略，可用「打开 每日复盘/YYYY-MM-DD」获取",
}

FOLDER_HINTS: dict[str, str] = {
    "投资方法论": "投资框架与方法",
    "市场分析": "大盘/板块/产业链分析",
    "每日复盘": "按日归档复盘",
    "内容源": "标的总览、追踪、决策时间线",
    "数据": "脚本输出（市场日报、标的池、粗筛/精筛 CSV）",
    "待审阅视频文稿": "bilibili_fetch / douyin_fetch 写入，待 txtcfm",
    "标的追踪": "活跃池标的专页",
    "不活跃标的": "已移出活跃池的追踪页",
}

FILE_HINTS: dict[str, str] = {
    "index.md": "Wiki 首页目录",
    "log.md": "ingest 变更日志",
}


def _hint(entry: Path, wiki_root: Path) -> str:
    if entry.is_dir():
        return FOLDER_HINTS.get(entry.name, "")
    rel = entry.relative_to(wiki_root).as_posix()
    return FILE_HINTS.get(entry.name, "") or FILE_HINTS.get(rel, "")


def _visible_entries(dir_path: Path) -> list[Path]:
    out: list[Path] = []
    for entry in sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if entry.name.startswith("."):
            continue
        if entry.is_file() and entry.name in SKIP_FILES:
            continue
        out.append(entry)
    return out


def _count_md_files(dir_path: Path) -> int:
    if not dir_path.is_dir():
        return 0
    return sum(1 for _ in dir_path.rglob("*.md"))


def build_wiki_tree(wiki_root: str = WIKI_ROOT) -> str:
    """生成 Wiki/ 目录树；「每日复盘」等目录仅显示摘要。"""
    root = Path(wiki_root)
    if not root.is_dir():
        return f"（Wiki 目录不存在：{wiki_root}）"

    lines = ["Wiki/"]

    def walk(dir_path: Path, prefix: str) -> None:
        entries = _visible_entries(dir_path)
        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            branch = "└── " if is_last else "├── "
            if entry.is_dir() and entry.name in COLLAPSE_DIRS:
                n = _count_md_files(entry)
                hint = _hint(entry, root)
                note = COLLAPSE_DIRS[entry.name]
                extra = f"{hint}；" if hint else ""
                suffix = f"  ← {extra}{n} 个 .md，{note}"
                lines.append(f"{prefix}{branch}{entry.name}/{suffix}")
                continue
            hint = _hint(entry, root)
            suffix = f"  ← {hint}" if hint else ""
            if entry.is_dir():
                lines.append(f"{prefix}{branch}{entry.name}/{suffix}")
                ext = "    " if is_last else "│   "
                walk(entry, prefix + ext)
            else:
                lines.append(f"{prefix}{branch}{entry.name}{suffix}")

    walk(root, "")
    return "\n".join(lines)


def _norm_query(q: str) -> str:
    q = q.strip().replace("\\", "/")
    if q.lower().startswith("wiki/"):
        q = q[5:]
    return q.removesuffix(".md").strip()


def find_wiki_md(query: str, wiki_root: str = WIKI_ROOT) -> list[Path]:
    """按相对路径 / 文件名 / 无后缀名匹配 Wiki 内 .md 文件。"""
    root = Path(wiki_root)
    if not root.is_dir():
        return []

    q = _norm_query(query)
    if not q:
        return []

    all_md = sorted(root.rglob("*.md"))
    exact: list[Path] = []
    stem_hits: list[Path] = []
    partial: list[Path] = []

    for path in all_md:
        rel = path.relative_to(root).as_posix()
        rel_no_ext = rel[:-3] if rel.endswith(".md") else rel
        name = path.name
        stem = path.stem

        if q == rel or q == rel_no_ext or q == name or q == stem:
            exact.append(path)
            continue
        if stem == q or name == f"{q}.md":
            stem_hits.append(path)
            continue
        if rel_no_ext.endswith(q) or q in rel_no_ext:
            partial.append(path)

    if exact:
        return exact
    if len(stem_hits) == 1:
        return stem_hits
    if stem_hits:
        return stem_hits
    if len(partial) == 1:
        return partial
    return partial
