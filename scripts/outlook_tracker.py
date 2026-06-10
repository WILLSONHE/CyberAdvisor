#!/usr/bin/env python3
"""1日/3日/7日技术倾向：登记、复盘、校准、批处理（sug / 分析报告 / daily / 持仓）。"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from typing import Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from outlook_paths import LOG_PATH, REVIEW_DIR, migrate_legacy_files

migrate_legacy_files()

HORIZONS = (1, 3, 7)
HORIZON_KEYS = tuple(f"{d}d" for d in HORIZONS)


def _today() -> date:
    return date.today()


def _parse_date(s: str) -> date:
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def _load_log() -> dict[str, Any]:
    if not os.path.isfile(LOG_PATH):
        return {"records": [], "meta": {"started": str(_today())}}
    try:
        return json.loads(open(LOG_PATH, encoding="utf-8").read())
    except (OSError, json.JSONDecodeError):
        return {"records": [], "meta": {}}


def _save_log(data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _records_for_code(code: str) -> list[dict[str, Any]]:
    code = str(code).zfill(6)
    return [r for r in _load_log().get("records", []) if str(r.get("code", "")).zfill(6) == code]


def has_any_prediction(code: str) -> bool:
    return bool(_records_for_code(code))


def _klines_in_window(code: str, start: date, end: date) -> list[dict[str, Any]]:
    from bollinger_utils import get_kline

    kl = get_kline(code, 90, min_bars=5)
    if kl is None or len(kl) == 0:
        return []
    rows: list[dict[str, Any]] = []
    for i in range(len(kl)):
        try:
            dt_raw = kl.iloc[i].get("datetime") or kl.iloc[i].get("date")
            if dt_raw is None:
                continue
            ds = str(dt_raw)[:10]
            d = _parse_date(ds)
        except (ValueError, TypeError):
            continue
        if start <= d <= end:
            rows.append(
                {
                    "date": ds,
                    "close": round(float(kl.iloc[i]["close"]), 2),
                    "high": round(float(kl.iloc[i].get("high", kl.iloc[i]["close"])), 2),
                    "low": round(float(kl.iloc[i].get("low", kl.iloc[i]["close"])), 2),
                }
            )
    return rows


def make_snapshot(
    code: str,
    *,
    name: str = "",
    holder: str = "",
    source: str = "sug",
    session: str = "",
    track_from: date | None = None,
) -> dict[str, Any] | None:
    from bollinger_utils import bollinger_for_code, export_outlook_horizon
    from outlook_params import load_params

    code = str(code).zfill(6)
    b = bollinger_for_code(code)
    if not b or b.get("error"):
        return None
    params = load_params()
    ke = b.get("kline_extra") or {}
    today = _today()
    if track_from is None:
        track_from = today
    horizons: dict[str, Any] = {}
    for d in HORIZONS:
        h = export_outlook_horizon(b, days=d, kline_extra=ke, params=params)
        due = track_from + timedelta(days=d)
        h["track_from"] = str(track_from)
        h["due_date"] = str(due)
        h["review"] = None
        horizons[f"{d}d"] = h
    return {
        "id": f"{today.isoformat()}_{code}_{holder or 'na'}_{source}",
        "date": str(today),
        "holder": holder,
        "source": source,
        "session": session,
        "code": code,
        "name": name or code,
        "price_at": b.get("price"),
        "zone_at": b.get("zone"),
        "horizons": horizons,
    }


def record_outlooks(
    codes: list[str],
    *,
    names: dict[str, str] | None = None,
    holder: str = "",
    source: str = "sug",
    session: str = "",
    track_from: date | None = None,
) -> list[str]:
    from outlook_universe import register_queried

    data = _load_log()
    names = names or {}
    added: list[str] = []
    for code in codes:
        code = str(code).zfill(6)
        nm = names.get(code, "")
        snap = make_snapshot(
            code,
            name=nm,
            holder=holder,
            source=source,
            session=session,
            track_from=track_from,
        )
        if not snap:
            continue
        data["records"].append(snap)
        added.append(code)
        if source in ("analysis_report", "qry", "chat"):
            register_queried(code, nm or code, source=source)
    _save_log(data)
    return added


def _top_level(levels: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not levels:
        return None
    return max(levels, key=lambda x: float(x.get("prob_pct") or 0))


def review_horizon(record: dict[str, Any], horizon_key: str) -> dict[str, Any] | None:
    h = (record.get("horizons") or {}).get(horizon_key)
    if not h:
        return None
    if h.get("review"):
        return h["review"]

    start = _parse_date(h.get("track_from") or record["date"])
    due = _parse_date(h["due_date"])
    if _today() < due:
        return None

    code = record["code"]
    bars = _klines_in_window(code, start, due)
    if not bars:
        return {"status": "pending", "reason": "窗口内无日K"}

    closes = [b["close"] for b in bars]
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    lo, hi = float(h["lo"]), float(h["hi"])
    anchor = float(h["anchor"])
    price_at = float(record.get("price_at") or closes[0])
    close_due = closes[-1]
    in_band_close = lo <= close_due <= hi
    range_touched = any(lo <= x <= hi for x in closes) or (min(lows) <= hi and max(highs) >= lo)
    top = _top_level(h.get("levels") or [])
    top_hit = False
    top_label = ""
    if top:
        tp = float(top["price"])
        top_label = str(top["label"])
        tol = tp * 0.015
        top_hit = any(abs(x - tp) <= tol for x in highs + lows + closes)

    review = {
        "status": "done",
        "reviewed_on": str(_today()),
        "window": f"{bars[0]['date']} ~ {bars[-1]['date']}",
        "actual_close": close_due,
        "actual_high": max(highs),
        "actual_low": min(lows),
        "in_band_close": in_band_close,
        "range_touched": range_touched,
        "top_level_label": top_label,
        "top_level_hit": top_hit,
        "anchor_error_pct": round((close_due - anchor) / price_at * 100, 2) if price_at else 0,
        "close_vs_predict_pct": round((close_due / price_at - 1) * 100, 2) if price_at else 0,
    }
    h["review"] = review
    return review


def review_due(
    *,
    holder: str | None = None,
    codes: list[str] | None = None,
    persist: bool = True,
) -> list[dict[str, Any]]:
    data = _load_log()
    results: list[dict[str, Any]] = []
    changed = False
    code_set = {str(c).zfill(6) for c in codes} if codes else None
    for rec in data.get("records", []):
        if holder and rec.get("holder") != holder:
            continue
        if code_set and str(rec.get("code", "")).zfill(6) not in code_set:
            continue
        for hk in HORIZON_KEYS:
            rev = review_horizon(rec, hk)
            if rev and rev.get("status") == "done":
                changed = True
                results.append({"record": rec, "horizon": hk, "review": rev})
    if persist and changed:
        _save_log(data)
    return results


def calibrate(*, min_samples: int = 3) -> dict[str, Any]:
    from outlook_params import load_params, save_params

    data = _load_log()
    params = load_params()
    notes: list[str] = []

    calib_rows = [
        ("1d", "band_hit_rate_1d", "top_level_hit_rate_1d"),
        ("3d", "band_hit_rate_3d", "top_level_hit_rate_3d"),
        ("7d", "band_hit_rate_7d", "top_level_hit_rate_7d"),
    ]
    for hk, stat_band, stat_top in calib_rows:
        hits_band: list[bool] = []
        hits_top: list[bool] = []
        for rec in data.get("records", []):
            h = (rec.get("horizons") or {}).get(hk) or {}
            rev = h.get("review")
            if not rev or rev.get("status") != "done":
                continue
            hits_band.append(bool(rev.get("in_band_close")))
            hits_top.append(bool(rev.get("top_level_hit")))
        if len(hits_band) < min_samples:
            notes.append(f"{hk} 样本 {len(hits_band)} < {min_samples}，跳过校准")
            continue
        rate_band = sum(hits_band) / len(hits_band)
        rate_top = sum(hits_top) / len(hits_top) if hits_top else 0
        params.setdefault("stats", {})[stat_band] = round(rate_band, 3)
        params.setdefault("stats", {})[stat_top] = round(rate_top, 3)

        bvs = float(params.get("band_vol_scale") or 1.0)
        if rate_band < 0.45:
            bvs = min(bvs + 0.05, 1.35)
            notes.append(f"{hk} 收盘落区间率 {rate_band:.0%} 偏低 → band_vol_scale {bvs:.2f}")
        elif rate_band > 0.92:
            bvs = max(bvs - 0.03, 0.85)
            notes.append(f"{hk} 收盘落区间率 {rate_band:.0%} 过高 → band_vol_scale {bvs:.2f}")
        params["band_vol_scale"] = round(bvs, 2)

        scale = float(params.get("prob_sigma_halfband_scale") or 0.92)
        boost = float(params.get("track_level_boost") or 1.25)
        if rate_top < 0.35:
            scale = max(scale - 0.05, 0.72)
            boost = min(boost + 0.04, 1.45)
            notes.append(
                f"{hk} 最高概率挡位命中率 {rate_top:.0%} 偏低 → prob_sigma_halfband_scale {scale:.2f}，"
                f"track_level_boost {boost:.2f}"
            )
        elif rate_top > 0.75:
            scale = min(scale + 0.05, 1.15)
            boost = max(boost - 0.03, 1.1)
            notes.append(
                f"{hk} 最高概率挡位命中率 {rate_top:.0%} 偏高 → prob_sigma_halfband_scale {scale:.2f}，"
                f"track_level_boost {boost:.2f}"
            )
        params["prob_sigma_halfband_scale"] = round(scale, 2)
        params["track_level_boost"] = round(boost, 2)

    params["version"] = str(_today())
    params.setdefault("stats", {})["reviews_total"] = sum(
        1
        for rec in data.get("records", [])
        for hk in HORIZON_KEYS
        if ((rec.get("horizons") or {}).get(hk) or {}).get("review", {}).get("status") == "done"
    )
    if notes:
        hist = params.setdefault("calibration_notes", [])
        hist.extend([f"[{params['version']}] " + n for n in notes])
        params["calibration_notes"] = hist[-20:]
    save_params(params)
    return {"params": params, "notes": notes}


def _live_judgment(code: str) -> str:
    from bollinger_utils import bollinger_for_code

    b = bollinger_for_code(code)
    if not b or b.get("error"):
        return "数据不足"
    return f"现价 {b.get('price')} | 布林 {b.get('zone')} | {b.get('bias', '')}"


def format_review_markdown(reviews: list[dict[str, Any]], *, holder: str = "") -> str:
    lines = ["## 八、预测复盘", ""]
    if holder:
        lines.append(f"> 持有人 **{holder}** | 复盘到期 1日/3日/7日 技术倾向")
    else:
        lines.append("> 复盘到期 1日/3日/7日 技术倾向")
    lines.append("")

    if not reviews:
        lines.append("**暂无到期预测待复盘**（或预测窗口尚未结束）。")
        lines.append("")
        return "\n".join(lines)

    for item in reviews:
        rec = item["record"]
        hk = item["horizon"]
        rev = item["review"]
        h = rec["horizons"][hk]
        ok_band = "是" if rev.get("in_band_close") else "否"
        ok_top = "是" if rev.get("top_level_hit") else "否"
        lines.append(
            f"### {rec.get('name')}（{rec['code']}）· {hk} · 预测日 {rec['date']}"
        )
        lines.append("")
        lines.append(
            f"- **预测区间**：{h['lo']}–{h['hi']}（{h['lo_pct']:+.1f}% ~ {h['hi_pct']:+.1f}%）| "
            f"锚点 {h['anchor']}（{h.get('anchor_pct', 0):+.1f}%）| 倾向 **{h.get('bias')}**"
        )
        ml = h.get("most_likely") or _top_level(h.get("levels") or [])
        if ml:
            lines.append(
                f"- **最有可能价位**：{ml['label']} **{ml['price']}**（较预测日 {ml.get('pct_vs_now', 0):+.1f}%，"
                f"倾向概率 {ml.get('prob_pct')}%）"
            )
        top = _top_level(h.get("levels") or [])
        if top:
            lines.append(
                f"- **最高概率挡位**：{top['label']} {top['price']}（{top['prob_pct']}%）→ 触及 **{ok_top}**"
            )
        lines.append(
            f"- **实际**（{rev.get('window')}）：收 {rev['actual_close']} | 高 {rev['actual_high']} | 低 {rev['actual_low']}"
        )
        lines.append(
            f"- **收盘落预测区间内**：**{ok_band}** | 锚点偏差 {rev.get('anchor_error_pct'):+.2f}% | "
            f"实际涨跌 {rev.get('close_vs_predict_pct'):+.2f}%"
        )
        if not rev.get("in_band_close"):
            if rev["actual_close"] > h["hi"]:
                lines.append("- **偏差**：强于预测上沿 → 下回可适当放宽区间或上修锚点权重")
            elif rev["actual_close"] < h["lo"]:
                lines.append("- **偏差**：弱于预测下沿 → 下回可加宽区间或下修锚点")
        lines.append("")

    from outlook_params import load_params

    p = load_params()
    st = p.get("stats") or {}
    if st.get("reviews_total"):
        lines.append("### 累计校准统计")
        lines.append("")
        lines.append(f"- 已复盘 **{st.get('reviews_total')}** 条 | 参数版本 `{p.get('version')}`")
        for k in (
            "band_hit_rate_1d",
            "band_hit_rate_3d",
            "band_hit_rate_7d",
            "top_level_hit_rate_1d",
            "top_level_hit_rate_3d",
            "top_level_hit_rate_7d",
        ):
            if st.get(k) is not None:
                lines.append(f"- {k}：**{st[k]:.1%}**")
        recent = (p.get("calibration_notes") or [])[-3:]
        if recent:
            lines.append("- 最近校准：" + "；".join(recent))
        lines.append("")

    lines.append(
        "> 复盘后运行 `python scripts/outlook_tracker.py calibrate` 可微调区间宽度与挡位权重"
        "（写入 `Wiki/数据/股价预测追踪/参数.json`）。"
    )
    return "\n".join(lines)


def run_batch(
    universe: str,
    *,
    session: str = "",
    source: str = "",
) -> dict[str, Any]:
    """批处理：复盘到期 + 无历史预测则登记（追踪自次日）+ 写复盘结论。"""
    from outlook_universe import iter_universe, names_map

    label_map = {
        "track": ("daily", "标的追踪"),
        "portfolio": ("sug_portfolio", "持仓.xlsx"),
    }
    batch_source, title = label_map.get(universe, (source or universe, universe))
    entries = iter_universe(universe)
    codes = [e.code for e in entries]
    nm = names_map(entries)

    reviews = review_due(codes=codes)
    cal_notes: list[str] = []
    if reviews:
        cal = calibrate(min_samples=3)
        cal_notes = cal.get("notes") or []

    tomorrow = _today() + timedelta(days=1)
    new_codes: list[str] = []
    skipped: list[str] = []
    for e in entries:
        if has_any_prediction(e.code):
            continue
        added = record_outlooks(
            [e.code],
            names={e.code: e.name},
            holder=e.holder,
            source=batch_source,
            session=session,
            track_from=tomorrow,
        )
        if added:
            new_codes.extend(added)
        else:
            skipped.append(f"{e.name}({e.code})")

    lines = [
        f"# 股价预测追踪 · {title}",
        "",
        f"- 日期：**{_today()}**",
        f"- 标的池：**{len(entries)}** 只 | 新登记：**{len(new_codes)}** | 到期复盘：**{len(reviews)}**",
        "",
    ]
    if new_codes:
        lines.append("## 新登记（无历史预测，追踪自次日）")
        lines.append("")
        for c in new_codes:
            lines.append(f"- {nm.get(c, c)}（{c}）")
        lines.append("")

    rev_md = format_review_markdown(reviews)
    if reviews:
        lines.append(rev_md.replace("## 八、预测复盘", "## 到期复盘"))
        lines.append("")

    lines.append("## 当前研判（布林快照）")
    lines.append("")
    lines.append("| 标的 | 代码 | 研判 |")
    lines.append("|------|------|------|")
    for e in entries:
        lines.append(f"| {e.name} | {e.code} | {_live_judgment(e.code)} |")
    lines.append("")

    if cal_notes:
        lines.append("## 自动校准")
        lines.append("")
        for n in cal_notes:
            lines.append(f"- {n}")
        lines.append("")

    if skipped:
        lines.append("## 跳过（无法生成预测）")
        lines.append("")
        for s in skipped:
            lines.append(f"- {s}")
        lines.append("")

    body = "\n".join(lines)
    os.makedirs(REVIEW_DIR, exist_ok=True)
    sess_tag = f"_{session}" if session else ""
    out_path = os.path.join(REVIEW_DIR, f"{_today().isoformat()}_{universe}{sess_tag}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(body)

    return {
        "universe": universe,
        "entries": len(entries),
        "reviews": len(reviews),
        "new_records": new_codes,
        "skipped": skipped,
        "review_file": out_path,
        "calibration_notes": cal_notes,
    }


def _codes_for_holder(holder: str) -> tuple[list[str], dict[str, str]]:
    from portfolio import HOLDINGS

    codes: list[str] = []
    names: dict[str, str] = {}
    for h in HOLDINGS:
        if h.get("holder") != holder:
            continue
        c = str(h["code"]).zfill(6)
        codes.append(c)
        names[c] = h.get("name", c)
    return codes, names


def main() -> int:
    parser = argparse.ArgumentParser(description="1日/3日/7日技术倾向追踪")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_rec = sub.add_parser("record", help="登记本次预测")
    p_rec.add_argument("--holder", default="")
    p_rec.add_argument("--code", action="append", default=[])
    p_rec.add_argument("--name", action="append", default=[])
    p_rec.add_argument("--source", default="sug", choices=("sug", "analysis_report", "qry", "daily", "sug_portfolio"))
    p_rec.add_argument("--session", default="")
    p_rec.add_argument("--track-from-tomorrow", action="store_true", help="追踪窗口自次日起算")

    p_rev = sub.add_parser("review", help="复盘到期预测")
    p_rev.add_argument("--holder", default="")
    p_rev.add_argument("--code", action="append", default=[])
    p_rev.add_argument("--universe", default="", choices=("", "track", "portfolio", "queried", "all"))

    sub.add_parser("calibrate", help="根据复盘结果微调参数")

    p_batch = sub.add_parser("batch", help="批处理：复盘 + 无历史则登记 + 写结论")
    p_batch.add_argument(
        "--universe",
        required=True,
        choices=("track", "portfolio", "all"),
        help="track=daily 标的追踪；portfolio=持仓.xlsx",
    )
    p_batch.add_argument("--session", default="")

    p_snap = sub.add_parser("snapshot", help="打印单标的预测快照 JSON")
    p_snap.add_argument("--code", required=True)
    p_snap.add_argument("--name", default="")

    p_reg = sub.add_parser("register-queried", help="登记询问过的标的（不生成预测）")
    p_reg.add_argument("--code", required=True)
    p_reg.add_argument("--name", default="")
    p_reg.add_argument("--source", default="chat", choices=("chat", "qry", "analysis_report"))

    args = parser.parse_args()

    if args.cmd == "record":
        codes = [str(c).zfill(6) for c in args.code]
        names: dict[str, str] = {}
        for i, c in enumerate(codes):
            if i < len(args.name):
                names[c] = args.name[i]
        if args.holder and not codes:
            codes, names = _codes_for_holder(args.holder)
        if not codes:
            print("无标的可登记", file=sys.stderr)
            return 1
        track_from = _today() + timedelta(days=1) if args.track_from_tomorrow else None
        added = record_outlooks(
            codes,
            names=names,
            holder=args.holder,
            source=args.source,
            session=args.session,
            track_from=track_from,
        )
        print(f"已登记 {len(added)} 只：{', '.join(added)} → {LOG_PATH}")
        return 0

    if args.cmd == "review":
        codes: list[str] | None
        if args.universe:
            from outlook_universe import iter_universe

            codes = [e.code for e in iter_universe(args.universe)]
        elif args.code:
            codes = [str(c).zfill(6) for c in args.code]
        else:
            codes = None
        reviews = review_due(holder=args.holder or None, codes=codes)
        print(format_review_markdown(reviews, holder=args.holder or ""))
        if reviews:
            cal = calibrate(min_samples=3)
            if cal.get("notes"):
                print("\n---\n**自动校准**：")
                for n in cal["notes"]:
                    print(f"- {n}")
        return 0

    if args.cmd == "calibrate":
        cal = calibrate()
        print(json.dumps(cal, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "batch":
        result = run_batch(args.universe, session=args.session)
        print(
            f"批处理完成 [{args.universe}]：{result['entries']} 只，"
            f"复盘 {result['reviews']}，新登记 {len(result['new_records'])}"
        )
        print(f"结论 → {result['review_file']}")
        if result["skipped"]:
            print("跳过：" + "；".join(result["skipped"][:8]))
        return 0

    if args.cmd == "snapshot":
        snap = make_snapshot(args.code, name=args.name)
        print(json.dumps(snap, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "register-queried":
        from outlook_universe import register_queried

        register_queried(args.code, args.name, source=args.source)
        print(f"已登记询问标的 {args.code} → Wiki/数据/股价预测追踪/询问标的.json")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
