"""每 15 分钟市场数据采集。"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime

SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from ai_sim.config import TICK_ROOT
from ai_sim.schedule_util import nearest_tick_label, tick_phase
from ai_sim.universe import UniverseEntry, build_universe
from market_daily.fetch import fetch_indices
from market_daily.supplement import build_supplement
from portfolio_utils import fetch_spot_price


def _quote_row(entry: UniverseEntry) -> dict:
    price = fetch_spot_price(entry.code)
    time.sleep(0.15)
    return {
        "name": entry.name,
        "code": entry.code,
        "source": entry.source,
        "price": price,
    }


def collect_tick(*, force_label: str = "") -> str:
    """采集一次 tick，写入 Raw/每15分钟市场数据/YYYY-MM-DD/HHMM.json"""
    now = datetime.now()
    day = now.strftime("%Y-%m-%d")
    label = force_label or nearest_tick_label(now)
    phase = tick_phase(tick_label=label)
    include_overnight = phase == "pre_open" or label in ("0915", "0930")
    out_dir = os.path.join(TICK_ROOT, day)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{label}.json")

    universe = build_universe()
    indices = fetch_indices()
    idx_rows = [
        {
            "name": q.name,
            "code": q.code,
            "close": q.close,
            "change_pct": q.change_pct,
            "open": q.open,
            "high": q.high,
            "low": q.low,
            "turnover_yi": q.turnover_yi,
        }
        for q in indices
    ]
    stocks = [_quote_row(e) for e in universe]

    try:
        supplement = build_supplement(include_overnight=include_overnight, kline_limit=20)
    except Exception as exc:
        supplement = {"error": str(exc)}

    payload = {
        "timestamp": now.isoformat(timespec="seconds"),
        "tick": label,
        "phase": phase,
        "indices": idx_rows,
        "universe_size": len(universe),
        "stocks": stocks,
        "supplement": supplement,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    md_path = out_path.replace(".json", ".md")
    lines = [
        f"# 每15分钟市场数据 {day} {label[:2]}:{label[2:]}",
        "",
        f"> 采集时间：{payload['timestamp']}",
        "",
        "## 指数",
        "",
        "| 指数 | 收盘 | 涨跌幅 |",
        "|------|------|--------|",
    ]
    for q in idx_rows:
        lines.append(f"| {q['name']} | {q['close']:.2f} | {q['change_pct']:+.2f}% |")
    lines.extend(["", "## 标的池现价", "", "| 标的 | 代码 | 来源 | 现价 |", "|------|------|------|------|"])
    for s in stocks:
        p = s["price"]
        ps = f"{p:.2f}" if p is not None else "—"
        lines.append(f"| {s['name']} | {s['code']} | {s['source']} | {ps} |")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return out_path
