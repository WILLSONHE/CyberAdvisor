"""Dashboard 只读数据层。"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from datetime import datetime
from typing import Any

import pandas as pd

from dashboard._paths import (
    BACKTEST_DIR,
    GRAPH_PROGRESS_DIR,
    GRAPH_RUNS_DIR,
    CHAN_GLOSSARY_MD,
    LOG_PATH,
    REVIEW_DIR,
    ROOT,
    SCRIPTS,
    SUG_VAULT,
)

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

SUG_FILE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})(?:_(\d{4}))?_(.+?)_sug(?: (早盘|午盘))?\.md$",
    re.IGNORECASE,
)


def all_holdings() -> list[dict[str, Any]]:
    import portfolio

    rows: list[dict[str, Any]] = []
    for h in portfolio.HOLDINGS:
        code = str(h.get("code", "")).zfill(6)
        rows.append(
            {
                "holder": h.get("holder", ""),
                "name": h.get("name", code),
                "code": code,
                "cost": h.get("cost"),
                "shares": h.get("shares"),
                "price": h.get("price"),
            }
        )
    return rows


def unique_codes() -> list[tuple[str, str]]:
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for h in all_holdings():
        c = h["code"]
        if c in seen:
            continue
        seen.add(c)
        out.append((c, h["name"]))
    return sorted(out, key=lambda x: x[0])


def load_kline_df(code: str, period: str = "day", *, limit: int = 120) -> pd.DataFrame | None:
    from chan.kline import get_bars

    raw = get_bars(code, period, limit=limit)
    if not raw.get("ok"):
        return None
    df: pd.DataFrame = raw["bars"].copy()
    if "time" not in df.columns and "datetime" in df.columns:
        df["time"] = df["datetime"].astype(str).str[:10]
    return df


def chan_snapshot(code: str, name: str = "", *, has_position: bool = False) -> dict[str, Any]:
    from chan.analyze import analyze_code

    return analyze_code(code, name=name, has_position=has_position)


def stock_verdict(code: str, name: str = "", *, has_position: bool = False) -> dict[str, Any]:
    from bollinger_utils import build_stock_verdict

    return build_stock_verdict(code, name=name, has_position=has_position)


def list_sug_reports() -> list[dict[str, str]]:
    if not os.path.isdir(SUG_VAULT):
        return []
    items: list[dict[str, str]] = []
    for path in glob.glob(os.path.join(SUG_VAULT, "*.md")):
        base = os.path.basename(path)
        m = SUG_FILE.match(base)
        if not m:
            continue
        items.append(
            {
                "path": path,
                "date": m.group(1),
                "hhmm": m.group(2) or "",
                "holder": m.group(3),
                "session": m.group(4) or "",
                "name": base,
            }
        )
    items.sort(key=lambda x: (x["date"], x["hhmm"], x["holder"]), reverse=True)
    return items


def read_text(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return f"（无法读取 {path}）"


def outlook_summary() -> dict[str, Any]:
    if not os.path.isfile(LOG_PATH):
        return {"records": 0, "reviewed": 0, "pending": 0}
    try:
        data = json.loads(open(LOG_PATH, encoding="utf-8").read())
    except (OSError, json.JSONDecodeError):
        return {"records": 0, "reviewed": 0, "pending": 0}
    records = data.get("records") or []
    reviewed = pending = 0
    for rec in records:
        horizons = rec.get("horizons") or {}
        for h in horizons.values():
            if not isinstance(h, dict):
                continue
            if h.get("review"):
                reviewed += 1
            elif h.get("due_date"):
                pending += 1
    return {
        "records": len(records),
        "reviewed": reviewed,
        "pending": pending,
        "params_path": os.path.join(os.path.dirname(LOG_PATH), "参数.json"),
    }


def list_outlook_reviews() -> list[str]:
    if not os.path.isdir(REVIEW_DIR):
        return []
    paths = glob.glob(os.path.join(REVIEW_DIR, "*.md"))
    paths.sort(reverse=True)
    return paths


def latest_backtest() -> dict[str, Any] | None:
    if not os.path.isdir(BACKTEST_DIR):
        return None
    jsons = sorted([f for f in os.listdir(BACKTEST_DIR) if f.endswith(".json")], reverse=True)
    if not jsons:
        return None
    path = os.path.join(BACKTEST_DIR, jsons[0])
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["_path"] = path
        data["_md"] = path[:-5] + ".md"
        return data
    except (OSError, json.JSONDecodeError):
        return None


def holders() -> list[str]:
    from portfolio_utils import load_holder_names

    return load_holder_names()


def graph_pipeline_enabled() -> bool:
    try:
        from graph.llm import graph_pipeline_enabled as _enabled

        return _enabled()
    except Exception:
        return False


def list_graph_progress(limit: int = 30) -> list[dict[str, Any]]:
    from graph.progress import list_recent_progress

    return list_recent_progress(limit)


def load_graph_progress(analysis_id: str) -> dict[str, Any] | None:
    from graph.progress import load_progress

    return load_progress(analysis_id)


def chan_glossary_markdown() -> str:
    if os.path.isfile(CHAN_GLOSSARY_MD):
        return read_text(CHAN_GLOSSARY_MD)
    return "（未找到 Wiki/投资方法论/缠论-术语与读表指南.md）"


def render_chan_glossary_expander(*, expanded: bool = False) -> None:
    """Streamlit 术语速查折叠框。"""
    import streamlit as st

    with st.expander("缠论术语速查（候选 / 保护 / 回测 / 矛盾组合）", expanded=expanded):
        st.markdown(chan_glossary_markdown())


def graph_run_markdown(analysis_id: str) -> str | None:
    path = os.path.join(GRAPH_RUNS_DIR, f"{analysis_id}.md")
    if os.path.isfile(path):
        return read_text(path)
    return None

