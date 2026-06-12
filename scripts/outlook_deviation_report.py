#!/usr/bin/env python3
"""1/3/7 预测 vs 实际收盘偏差分析。"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from statistics import mean, median

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from outlook_tracker import HORIZON_KEYS, _top_level, _load_log, _parse_date, _today
from outlook_universe import iter_universe, names_map
from portfolio_utils import fetch_spot_price
from tdx_vipdoc import read_daily_bars


def _close_on(code: str, target: date) -> tuple[float | None, str]:
    """返回 (收盘价, 来源说明)。"""
    df = read_daily_bars(code, limit=10)
    if df is not None and not df.empty:
        for i in range(len(df) - 1, -1, -1):
            ds = str(df.iloc[i].get("datetime") or df.iloc[i].get("date") or "")[:10]
            try:
                d = datetime.strptime(ds, "%Y-%m-%d").date()
            except ValueError:
                continue
            if d == target:
                return round(float(df.iloc[i]["close"]), 2), f"vipdoc {ds}"
            if d < target:
                break
        last_ds = str(df.iloc[-1].get("datetime") or df.iloc[-1].get("date") or "")[:10]
        last_close = round(float(df.iloc[-1]["close"]), 2)
        if last_ds:
            return last_close, f"vipdoc最新 {last_ds}"
    spot = fetch_spot_price(code)
    if spot:
        return round(float(spot), 2), "行情spot"
    return None, "无数据"


def _latest_due_records(target: date) -> list[dict]:
    """每个 (code, horizon) 取 due_date==target 且最新的一条。"""
    data = _load_log()
    best: dict[tuple[str, str], dict] = {}
    for rec in data.get("records", []):
        code = str(rec.get("code", "")).zfill(6)
        for hk in HORIZON_KEYS:
            h = (rec.get("horizons") or {}).get(hk)
            if not h:
                continue
            due = h.get("due_date")
            if not due or _parse_date(str(due)) != target:
                continue
            key = (code, hk)
            if key not in best or rec.get("date", "") >= best[key]["record"].get("date", ""):
                best[key] = {"record": rec, "horizon": hk, "h": h}
    return list(best.values())


def _jun12_predictions() -> dict[str, dict]:
    """12日登记的预测（track+portfolio）。"""
    data = _load_log()
    today = str(_today())
    out: dict[str, dict] = {}
    for rec in data.get("records", []):
        if rec.get("date") != today:
            continue
        code = str(rec.get("code", "")).zfill(6)
        if code not in out or rec.get("source") == "daily":
            out[code] = rec
    return out


def main() -> None:
    target = _today()
    entries = iter_universe("track") + iter_universe("portfolio")
    nm = names_map(entries)
    track_codes = {e.code for e in iter_universe("track")}
    port_codes = {e.code for e in iter_universe("portfolio")}

    due_items = _latest_due_records(target)
    jun12_preds = _jun12_predictions()

    rows_due: list[dict] = []
    for item in due_items:
        rec = item["record"]
        hk = item["horizon"]
        h = item["h"]
        code = str(rec["code"]).zfill(6)
        actual, src = _close_on(code, target)
        if actual is None:
            continue
        anchor = float(h["anchor"])
        ml = h.get("most_likely") or _top_level(h.get("levels") or [])
        ml_price = float(ml["price"]) if ml else anchor
        price_at = float(rec.get("price_at") or actual)
        rows_due.append(
            {
                "code": code,
                "name": rec.get("name") or nm.get(code, code),
                "pool": "track" if code in track_codes else "portfolio",
                "horizon": hk,
                "pred_date": rec.get("date"),
                "price_at": price_at,
                "lo": float(h["lo"]),
                "hi": float(h["hi"]),
                "anchor": anchor,
                "most_likely": ml_price,
                "most_likely_label": ml.get("label", "") if ml else "",
                "actual": actual,
                "actual_src": src,
                "anchor_err_pct": round((actual - anchor) / price_at * 100, 2),
                "ml_err_pct": round((actual - ml_price) / price_at * 100, 2),
                "in_band": float(h["lo"]) <= actual <= float(h["hi"]),
                "bias": h.get("bias", ""),
            }
        )

    missing_j12 = []
    for e in iter_universe("track"):
        if e.code not in jun12_preds:
            missing_j12.append(e.code)

    report = {
        "as_of": str(target),
        "due_date": str(target),
        "vipdoc_note": "若 vipdoc 无当日 .day，实际价取 vipdoc 最新 bar 或 spot",
        "due_review_count": len(rows_due),
        "jun12_pred_track": len([c for c in jun12_preds if c in track_codes]),
        "jun12_pred_total": len(jun12_preds),
        "track_universe": len(track_codes),
        "missing_jun12_track": [f"{nm.get(c,c)}({c})" for c in missing_j12],
        "rows_due": rows_due,
        "summary_by_horizon": {},
    }

    for hk in ("1d", "3d", "7d"):
        sub = [r for r in rows_due if r["horizon"] == hk]
        if not sub:
            continue
        report["summary_by_horizon"][hk] = {
            "n": len(sub),
            "band_hit_pct": round(100 * sum(1 for r in sub if r["in_band"]) / len(sub), 1),
            "mae_anchor_pct": round(mean(abs(r["anchor_err_pct"]) for r in sub), 2),
            "mae_ml_pct": round(mean(abs(r["ml_err_pct"]) for r in sub), 2),
            "median_anchor_err_pct": round(median(r["anchor_err_pct"] for r in sub), 2),
        }

    out_path = os.path.join(
        SCRIPT_DIR, "..", "Wiki", "数据", "股价预测追踪", f"复盘_{target}_偏差分析.json"
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
