"""缠论结构启发式分析（日线 + 60min 级别联立）。"""
from __future__ import annotations

from typing import Any

import pandas as pd

from chan.indicators import compare_macd_divergence, compute_macd, find_swing_points
from chan.kline import PERIOD_LABEL, get_bars


def _trend_label(df: pd.DataFrame) -> str:
    """简化：近段高低点序列。"""
    tail = df.tail(60)
    lows = tail["low"]
    highs = tail["high"]
    bots, tops = find_swing_points(lows, highs, window=2)
    if len(bots) >= 2 and len(tops) >= 2:
        lb1, lb2 = float(lows.iloc[bots[-2]]), float(lows.iloc[bots[-1]])
        hb1, hb2 = float(highs.iloc[tops[-2]]), float(highs.iloc[tops[-1]])
        if lb2 > lb1 and hb2 > hb1:
            return "上涨"
        if lb2 < lb1 and hb2 < hb1:
            return "下跌"
    rng = float(tail["high"].max() - tail["low"].min())
    if rng <= 0:
        return "盘整"
    mid = (float(tail["high"].max()) + float(tail["low"].min())) / 2
    last = float(tail["close"].iloc[-1])
    if abs(last - mid) / rng < 0.25:
        return "盘整"
    return "上涨" if last > mid else "下跌"


def _pivot_zone(df: pd.DataFrame) -> dict[str, float]:
    tail = df.tail(40)
    zg = float(tail["high"].quantile(0.75))
    zd = float(tail["low"].quantile(0.25))
    return {"ZD": round(zd, 3), "ZG": round(zg, 3)}


def _buy_point_hint(
    day_df: pd.DataFrame,
    h60_df: pd.DataFrame | None,
    *,
    trend: str,
) -> tuple[str, str]:
    down_div = compare_macd_divergence(day_df, direction="down")
    up_div = compare_macd_divergence(day_df, direction="up")
    close = float(day_df["close"].iloc[-1])
    zone = _pivot_zone(day_df)
    zd, zg = zone["ZD"], zone["ZG"]

    if trend == "下跌" and down_div.get("divergence"):
        return "一买候选", "日线下跌趋势 + MACD 面积不创新低（趋势背驰）"

    bots, _ = find_swing_points(day_df["low"], day_df["high"], window=2)
    if bots:
        last_low = float(day_df["low"].iloc[bots[-1]])
        if trend in ("上涨", "盘整") and close > last_low * 1.01 and close < zg:
            if h60_df is not None and len(h60_df) >= 30:
                sub = compare_macd_divergence(h60_df, direction="down")
                if sub.get("divergence"):
                    return "二买候选", "日线反弹后回调 + 60min 盘整/趋势背驰"
            return "二买候选", "回调未破前低，日线结构转强"

    if close > zg * 1.005:
        recent = day_df.tail(15)
        pull = float(recent["low"].min())
        if pull >= zg * 0.995:
            return "三买候选", f"离开中枢后回抽未破 ZG（≈{zg}）"

    if trend == "上涨" and up_div.get("divergence"):
        return "一卖/减仓", "日线上涨 + 顶背驰"

    if close < zd:
        return "观望/空", f"价格低于中枢下沿 ZD≈{zd}"

    return "无明确买卖点", "结构未完成或处于中枢震荡"


def _action_from_hint(hint: str, *, has_position: bool) -> str:
    if hint.startswith("一买") or hint.startswith("二买") or hint.startswith("三买"):
        return "buy" if not has_position else "hold_add"
    if hint.startswith("一卖") or hint.startswith("观望/空"):
        return "sell" if has_position else "wait"
    return "hold" if has_position else "wait"


def _score(hint: str, action: str) -> float:
    table = {
        "三买候选": 2.0,
        "二买候选": 1.6,
        "一买候选": 1.0,
        "无明确买卖点": 0.0,
        "观望/空": -1.2,
        "一卖/减仓": -1.8,
    }
    base = table.get(hint, 0.0)
    if action == "sell":
        return min(base, -1.0)
    return base


def _analyze_period(code: str, period: str, *, limit: int | None = None) -> dict[str, Any]:
    raw = get_bars(code, period, limit=limit)
    if not raw.get("ok"):
        return {"ok": False, "period": period, "error": raw.get("error")}
    df: pd.DataFrame = raw["bars"]
    trend = _trend_label(df)
    zone = _pivot_zone(df)
    macd = compute_macd(df["close"])
    last_hist = float(macd["hist"].iloc[-1])
    return {
        "ok": True,
        "period": period,
        "label": PERIOD_LABEL[period],
        "source": raw.get("source"),
        "bar_count": raw.get("bar_count"),
        "last_time": raw.get("last_time"),
        "last_close": raw.get("last_close"),
        "trend": trend,
        "ZD": zone["ZD"],
        "ZG": zone["ZG"],
        "macd_hist": round(last_hist, 4),
        "macd_above_zero": float(macd["dif"].iloc[-1]) > 0,
    }


def analyze_code(
    code: str,
    *,
    name: str = "",
    has_position: bool = False,
) -> dict[str, Any]:
    """单标的缠论快照（报告/模拟盘共用）。"""
    code = str(code).zfill(6)
    day = get_bars(code, "day", limit=240)
    h60 = get_bars(code, "60m", limit=240)
    if not day.get("ok"):
        return {
            "ok": False,
            "code": code,
            "name": name or code,
            "error": day.get("error", "日K不足"),
        }

    day_df: pd.DataFrame = day["bars"]
    h60_df: pd.DataFrame | None = h60["bars"] if h60.get("ok") else None
    trend = _trend_label(day_df)
    zone = _pivot_zone(day_df)
    hint, hint_reason = _buy_point_hint(day_df, h60_df, trend=trend)
    action = _action_from_hint(hint, has_position=has_position)
    score = _score(hint, action)
    down_div = compare_macd_divergence(day_df, direction="down")
    up_div = compare_macd_divergence(day_df, direction="up")

    protect = zone["ZD"]
    if "二买" in hint and down_div.get("price2"):
        protect = down_div["price2"]
    elif "三买" in hint:
        protect = zone["ZG"]

    sources = {"day": day.get("source")}
    if h60.get("ok"):
        sources["60m"] = h60.get("source")

    return {
        "ok": True,
        "code": code,
        "name": name or code,
        "trend_day": trend,
        "structure": "盘整" if trend == "盘整" else f"{trend}趋势",
        "ZD": zone["ZD"],
        "ZG": zone["ZG"],
        "buy_point": hint,
        "buy_reason": hint_reason,
        "action": action,
        "score": score,
        "protect_price": protect,
        "divergence_down": down_div,
        "divergence_up": up_div,
        "levels": {
            "day": _analyze_period(code, "day", limit=240),
            "60m": _analyze_period(code, "60m", limit=240) if h60.get("ok") else {"ok": False, "error": h60.get("error")},
            "30m": _analyze_period(code, "30m", limit=120),
        },
        "sources": sources,
        "priority_note": "缠论为第一优先级；布林/outlook 仅作辅助",
    }


def analyze_index(code: str = "000001", *, name: str = "上证指数") -> dict[str, Any]:
    return analyze_code(code, name=name, has_position=False)
