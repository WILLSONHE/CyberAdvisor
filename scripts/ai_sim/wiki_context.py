"""为 Cloud Agent 组装 Wiki 策略上下文（覆盖全库索引 + 核心策略全文/摘要）。"""
from __future__ import annotations

import os
import re
from pathlib import Path

from ai_sim.config import DAILY_REPORT, ROOT

WIKI_ROOT = os.path.join(ROOT, "Wiki")
STRATEGY_MD = os.path.join(WIKI_ROOT, "数据", "AI模拟盘策略.md")
INDEX_DISCIPLINE_MD = os.path.join(WIKI_ROOT, "投资方法论", "指数纪律框架.md")
MARKET_HISTORY_MD = os.path.join(WIKI_ROOT, "市场分析", "大盘研判历史.md")
DAILY_REVIEW_DIR = os.path.join(WIKI_ROOT, "每日复盘")

_DAILY_REVIEW_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")

# 每 tick 必读（策略与框架）；最新日更 / 指数纪律在 build 时动态插入
CORE_READ_PATHS: tuple[str, ...] = (
    STRATEGY_MD,
    INDEX_DISCIPLINE_MD,
    os.path.join(WIKI_ROOT, "投资方法论", "宏观分析框架.md"),
    os.path.join(WIKI_ROOT, "投资方法论", "选股框架.md"),
    os.path.join(WIKI_ROOT, "投资方法论", "仓位管理.md"),
    os.path.join(WIKI_ROOT, "投资方法论", "风控逻辑.md"),
    MARKET_HISTORY_MD,
    DAILY_REPORT,
    os.path.join(WIKI_ROOT, "其他材料", "_index.md"),
)

SKIP_PARTS = ("_extracts",)
SKIP_NAMES = frozenset({"feishu_debug.log"})


def latest_daily_review_path() -> str | None:
    """最近一篇标准日更 `YYYY-MM-DD.md`（不含专题后缀页）。"""
    if not os.path.isdir(DAILY_REVIEW_DIR):
        return None
    names = [n for n in os.listdir(DAILY_REVIEW_DIR) if _DAILY_REVIEW_NAME.match(n)]
    if not names:
        return None
    return os.path.join(DAILY_REVIEW_DIR, sorted(names)[-1])


def core_read_paths() -> list[str]:
    paths = list(CORE_READ_PATHS)
    latest = latest_daily_review_path()
    if latest:
        # 紧接策略与指数纪律之后注入最新日更
        insert_at = 2 if paths[1] == INDEX_DISCIPLINE_MD else 1
        paths.insert(insert_at, latest)
    return paths


def _read_slice(path: str, *, max_chars: int) -> str:
    if not os.path.isfile(path):
        return f"（缺失：{os.path.relpath(path, ROOT)}）\n"
    text = open(path, encoding="utf-8").read()
    if len(text) <= max_chars:
        return text
    head = text[: max_chars // 2]
    tail = text[-max_chars // 2 :]
    return head + "\n\n…（中间省略）…\n\n" + tail


def iter_wiki_md() -> list[str]:
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(WIKI_ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_PARTS]
        for name in filenames:
            if not name.endswith(".md") or name in SKIP_NAMES:
                continue
            out.append(os.path.join(dirpath, name))
    return sorted(out)


def wiki_manifest() -> str:
    lines = ["## Wiki 全库索引（须知晓存在；细节按需引用）", ""]
    for path in iter_wiki_md():
        rel = os.path.relpath(path, WIKI_ROOT).replace("\\", "/")
        lines.append(f"- `Wiki/{rel}`")
    lines.append(f"\n共 **{len(lines) - 3}** 个 markdown 页面。")
    latest = latest_daily_review_path()
    if latest:
        rel = os.path.relpath(latest, WIKI_ROOT).replace("\\", "/")
        lines.append(f"\n**最新日更（必读）**：`Wiki/{rel}`")
    return "\n".join(lines)


def build_wiki_context(*, max_chars: int = 16000) -> str:
    """策略文件 + 核心框架 + 全库清单；总长截断时优先保留策略与清单。"""
    parts: list[str] = []
    budget = max_chars

    manifest = wiki_manifest()
    parts.append(manifest)
    budget -= len(manifest)

    paths = core_read_paths()
    per_core = max(1200, budget // max(len(paths), 1))
    for path in paths:
        rel = os.path.relpath(path, ROOT)
        block = f"\n---\n### `{rel}`\n\n" + _read_slice(path, max_chars=per_core)
        parts.append(block)
        budget -= len(block)
        if budget <= 0:
            break

    text = "\n".join(parts)
    if len(text) > max_chars:
        return text[:max_chars] + "\n…（Wiki 上下文截断）\n"
    return text
