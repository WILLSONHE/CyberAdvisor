"""1日/3日/7日预测追踪：标的池（标的追踪 / 持仓.xlsx / 询问标的）。"""
from __future__ import annotations

import csv
import json
import os
import sys
from dataclasses import dataclass
from datetime import date
from typing import Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
from wiki.common import TRACK_DIR, TRACK_INACTIVE_DIR as TRACK_INACTIVE  # noqa: E402
COARSE_CSV = os.path.join(ROOT, "Wiki", "数据", "粗筛结果.csv")
XLSX_PATH = os.path.join(ROOT, "持仓.xlsx")

from outlook_paths import PREDICT_DIR, QUERIED_PATH  # noqa: E402

# 粗筛 CSV 未覆盖的追踪页名称 → 代码
EXTRA_NAME_CODES: dict[str, str] = {
    "汇绿生态": "001267",
    "东阳光": "600673",
    "东山精密": "002384",
    "天孚通信": "300394",
    "德明利": "001309",
    "宏景科技": "301396",
    "新易盛": "300502",
    "润泽科技": "300442",
    "网宿科技": "300017",
}


@dataclass(frozen=True)
class SymbolEntry:
    code: str
    name: str
    pool: str  # track | portfolio | queried
    holder: str = ""


def _track_code_map() -> dict[str, str]:
    try:
        from fine_screen import TRACK_STOCKS

        return dict(TRACK_STOCKS)
    except Exception:
        return {}


def _coarse_name_map() -> dict[str, str]:
    out: dict[str, str] = {}
    if not os.path.isfile(COARSE_CSV):
        return out
    try:
        with open(COARSE_CSV, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                name = (row.get("name") or "").strip()
                code = str(row.get("code") or "").strip().zfill(6)
                if name and len(code) == 6:
                    out[name] = code
    except OSError:
        pass
    return out


def resolve_name_to_code(name: str) -> str:
    """追踪页文件名（或显示名）→ A 股 6 位代码。"""
    name = name.strip()
    if name.startswith("股性-"):
        name = name[3:]
    m = _track_code_map()
    m.update(EXTRA_NAME_CODES)
    m.update(_coarse_name_map())
    return m.get(name, "")


def _iter_track_stems() -> list[str]:
    stems: list[str] = []
    for base in (TRACK_DIR, TRACK_INACTIVE):
        if not os.path.isdir(base):
            continue
        for f in os.listdir(base):
            if not f.endswith(".md"):
                continue
            stem = f[:-3]
            if stem.startswith("股性-"):
                stem = stem[3:]
            stems.append(stem)
    return sorted(set(stems))


def iter_track_symbols(*, include_inactive: bool = True) -> list[SymbolEntry]:
    stems = _iter_track_stems() if include_inactive else [
        s for s in _iter_track_stems()
        if os.path.isfile(os.path.join(TRACK_DIR, f"{s}.md"))
        or os.path.isfile(os.path.join(TRACK_DIR, f"股性-{s}.md"))
    ]
    out: list[SymbolEntry] = []
    seen: set[str] = set()
    for name in stems:
        code = resolve_name_to_code(name)
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(SymbolEntry(code=code, name=name, pool="track"))
    return out


def iter_portfolio_symbols() -> list[SymbolEntry]:
    from portfolio_utils import classify_market, normalize_stock_code, resolve_a_share_proxy

    holdings: list[dict[str, Any]]
    if os.path.isfile(XLSX_PATH):
        from sync_portfolio_from_xlsx import _read_holdings

        holdings, _, _ = _read_holdings(XLSX_PATH)
    else:
        from portfolio import HOLDINGS

        holdings = list(HOLDINGS)

    out: list[SymbolEntry] = []
    seen: set[str] = set()
    for h in holdings:
        raw = normalize_stock_code(str(h["code"]))
        mkt = classify_market(raw)
        a_code = resolve_a_share_proxy(raw, explicit_proxy=h.get("a_share_proxy"))
        if mkt in ("sh", "sz", "bj"):
            kline_code = raw
        elif a_code:
            kline_code = a_code
        else:
            continue
        if kline_code in seen:
            continue
        seen.add(kline_code)
        out.append(
            SymbolEntry(
                code=kline_code,
                name=str(h.get("name") or kline_code),
                pool="portfolio",
                holder=str(h.get("holder") or ""),
            )
        )
    return out


def _load_queried_raw() -> dict[str, Any]:
    if not os.path.isfile(QUERIED_PATH):
        return {"symbols": [], "meta": {"note": "用户询问过的标的（qry / 分析报告 / record --code）"}}
    try:
        return json.loads(open(QUERIED_PATH, encoding="utf-8").read())
    except (OSError, json.JSONDecodeError):
        return {"symbols": []}


def _save_queried_raw(data: dict[str, Any]) -> None:
    os.makedirs(PREDICT_DIR, exist_ok=True)
    with open(QUERIED_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def register_queried(code: str, name: str = "", *, source: str = "unknown") -> None:
    code = str(code).zfill(6)
    today = str(date.today())
    data = _load_queried_raw()
    symbols: list[dict[str, Any]] = list(data.get("symbols") or [])
    for s in symbols:
        if str(s.get("code", "")).zfill(6) == code:
            s["last_seen"] = today
            if name:
                s["name"] = name
            if source:
                s["source"] = source
            _save_queried_raw(data)
            return
    symbols.append(
        {
            "code": code,
            "name": name or code,
            "first_seen": today,
            "last_seen": today,
            "source": source,
        }
    )
    data["symbols"] = symbols
    _save_queried_raw(data)


def iter_queried_symbols() -> list[SymbolEntry]:
    out: list[SymbolEntry] = []
    for s in _load_queried_raw().get("symbols") or []:
        code = str(s.get("code", "")).zfill(6)
        if len(code) != 6:
            continue
        out.append(
            SymbolEntry(
                code=code,
                name=str(s.get("name") or code),
                pool="queried",
            )
        )
    return out


def iter_universe(kind: str) -> list[SymbolEntry]:
    """kind: track | portfolio | queried | all"""
    if kind == "track":
        return iter_track_symbols(include_inactive=True)
    if kind == "portfolio":
        return iter_portfolio_symbols()
    if kind == "queried":
        return iter_queried_symbols()
    if kind == "all":
        seen: set[str] = set()
        merged: list[SymbolEntry] = []
        for pool in ("track", "portfolio", "queried"):
            for e in iter_universe(pool):
                if e.code in seen:
                    continue
                seen.add(e.code)
                merged.append(e)
        return merged
    raise ValueError(f"未知 universe: {kind}")


def names_map(entries: list[SymbolEntry]) -> dict[str, str]:
    return {e.code: e.name for e in entries}
