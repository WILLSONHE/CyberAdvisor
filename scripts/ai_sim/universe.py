"""AI 模拟盘标的池：活跃追踪 + 市场状态日报强势板块成分。"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from ai_sim.config import DAILY_REPORT, TRACK_DIR


@dataclass(frozen=True)
class UniverseEntry:
    name: str
    code: str
    source: str  # track | daily_gain | daily_loss


def _active_track_names() -> list[str]:
    if not os.path.isdir(TRACK_DIR):
        return []
    return sorted(
        f[:-3]
        for f in os.listdir(TRACK_DIR)
        if f.endswith(".md") and not f.startswith("股性-")
    )


def _track_code_map() -> dict[str, str]:
    import sys

    scripts = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    try:
        from fine_screen import TRACK_STOCKS

        return dict(TRACK_STOCKS)
    except Exception:
        return {}


def _parse_daily_board_stocks(path: str, *, gain_only: bool = True) -> list[tuple[str, str]]:
    """从市场状态日报第三节表格解析 标的|代码。"""
    if not os.path.isfile(path):
        return []
    text = open(path, encoding="utf-8").read()
    section = "3.1" if gain_only else "3.2"
    marker = f"### {section}"
    if marker not in text:
        return []
    part = text.split(marker, 1)[1]
    if gain_only and "### 3.2" in part:
        part = part.split("### 3.2", 1)[0]
    rows: list[tuple[str, str]] = []
    for line in part.splitlines():
        if not line.strip().startswith("|") or "---" in line:
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) < 2 or cols[0] in ("标的", ""):
            continue
        name, code = cols[0], re.sub(r"\D", "", cols[1])[:6]
        if name and len(code) == 6:
            rows.append((name, code))
    return rows


def build_universe() -> list[UniverseEntry]:
    code_map = _track_code_map()
    seen: set[str] = set()
    out: list[UniverseEntry] = []

    def add(name: str, code: str, source: str) -> None:
        code = code.zfill(6)
        key = code
        if key in seen:
            return
        seen.add(key)
        out.append(UniverseEntry(name=name, code=code, source=source))

    for name in _active_track_names():
        code = code_map.get(name, "")
        if code:
            add(name, code, "track")

    for name, code in _parse_daily_board_stocks(DAILY_REPORT, gain_only=True):
        add(name, code, "daily_gain")

    for name, code in _parse_daily_board_stocks(DAILY_REPORT, gain_only=False):
        add(name, code, "daily_loss")

    return out
