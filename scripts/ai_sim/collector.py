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
from ai_sim.supplement_registry import build_supplement_payload
from ai_sim.supplement_state import enabled_metrics
from ai_sim.universe import UniverseEntry, build_universe
from bollinger_utils import _outlook_3d_7d, bollinger_for_code
from market_daily.fetch import fetch_indices
from portfolio_utils import fetch_spot_price
from report_data import fetch_vipdoc_stats


def _quote_row(entry: UniverseEntry) -> dict:
    price = fetch_spot_price(entry.code)
    time.sleep(0.15)
    boll = bollinger_for_code(entry.code)
    row = {
        "name": entry.name,
        "code": entry.code,
        "source": entry.source,
        "price": price,
    }
    vip = fetch_vipdoc_stats(entry.code)
    if vip and not vip.get("error"):
        row["vipdoc"] = vip
    try:
        from chan.analyze import analyze_code
        from chan.policy import compact_chan

        ch = analyze_code(entry.code, name=entry.name)
        row["chan"] = compact_chan(ch)
    except Exception:
        pass
    if boll and "error" not in boll:
        row["boll_zone"] = boll.get("zone")
        row["boll_signal"] = boll.get("signal")
        row["boll_mid"] = boll.get("mid")
        row["boll_track2"] = boll.get("track2")
        row["boll_track4"] = boll.get("track4")
        row["boll_track5"] = boll.get("track5")
        row["boll_top"] = boll.get("top")
        row["boll_bot"] = boll.get("bot")
        try:
            outlook = _outlook_3d_7d(boll, kline_extra=boll.get("kline_extra"))
            for hk, ok in (("1d", "d1_most_likely"), ("3d", "d3_most_likely"), ("7d", "d7_most_likely")):
                ml = outlook.get(ok)
                if ml:
                    row[f"outlook_{hk}"] = ml
        except Exception:
            pass
    return row


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
    index_chan = {}
    try:
        from chan.analyze import analyze_index
        from chan.policy import compact_chan

        index_chan = compact_chan(analyze_index())
    except Exception:
        pass

    stocks = [_quote_row(e) for e in universe]

    try:
        supplement = build_supplement_payload(
            enabled_metrics(),
            include_overnight=include_overnight,
            kline_limit=20,
        )
    except Exception as exc:
        supplement = {"error": str(exc)}

    payload = {
        "timestamp": now.isoformat(timespec="seconds"),
        "tick": label,
        "phase": phase,
        "indices": idx_rows,
        "index_chan": index_chan,
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
    if index_chan.get("ok"):
        lines.extend([
            "",
            f"> **缠论·上证（第一优先级）**：{index_chan.get('structure')} | {index_chan.get('buy_point')} | "
            f"动作={index_chan.get('action')} | 保护≈{index_chan.get('protect_price')}",
        ])
    lines.extend(["", "## 标的池现价", "", "| 标的 | 代码 | 来源 | 现价 |", "|------|------|------|------|"])
    for s in stocks:
        p = s["price"]
        ps = f"{p:.2f}" if p is not None else "—"
        lines.append(f"| {s['name']} | {s['code']} | {s['source']} | {ps} |")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return out_path
