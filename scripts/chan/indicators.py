"""MACD 与力度比较。"""
from __future__ import annotations

import pandas as pd


def compute_macd(
    closes: pd.Series,
    *,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    hist = (dif - dea) * 2
    return pd.DataFrame({"dif": dif, "dea": dea, "hist": hist})


def hist_area(hist: pd.Series, start: int, end: int) -> float:
    seg = hist.iloc[start : end + 1]
    if seg.empty:
        return 0.0
    return float(seg.abs().sum())


def find_swing_points(
    lows: pd.Series,
    highs: pd.Series,
    *,
    window: int = 3,
) -> tuple[list[int], list[int]]:
    """简化局部极值索引。"""
    bot_idx: list[int] = []
    top_idx: list[int] = []
    n = len(lows)
    for i in range(window, n - window):
        if lows.iloc[i] <= lows.iloc[i - window : i + window + 1].min():
            bot_idx.append(i)
        if highs.iloc[i] >= highs.iloc[i - window : i + window + 1].max():
            top_idx.append(i)
    return bot_idx, top_idx


def compare_macd_divergence(
    df: pd.DataFrame,
    *,
    direction: str = "down",
    lookback: int = 80,
) -> dict:
    """
    比较最近两段同向 MACD 柱面积。
    direction=down → 一买区；up → 一卖区。
    """
    work = df.tail(lookback).reset_index(drop=True)
    if len(work) < 40:
        return {"divergence": False, "reason": "样本不足"}
    macd = compute_macd(work["close"])
    hist = macd["hist"]
    lows = work["low"]
    highs = work["high"]
    bots, tops = find_swing_points(lows, highs, window=2)

    if direction == "down":
        pivots = [i for i in bots if i >= 10][-3:]
        if len(pivots) < 2:
            return {"divergence": False, "reason": "底分型不足"}
        i1, i2 = pivots[-2], pivots[-1]
        p1, p2 = float(lows.iloc[i1]), float(lows.iloc[i2])
        if p2 > p1 * 0.998:
            return {"divergence": False, "reason": "未创新低"}
        a1 = hist_area(hist, max(0, i1 - 8), i1)
        a2 = hist_area(hist, max(0, i2 - 8), i2)
        div = a2 < a1 * 0.85 and a1 > 0
        return {
            "divergence": div,
            "kind": "趋势背驰" if div else "无",
            "price1": round(p1, 3),
            "price2": round(p2, 3),
            "area1": round(a1, 4),
            "area2": round(a2, 4),
            "pivot_idx": (i1, i2),
        }

    pivots = [i for i in tops if i >= 10][-3:]
    if len(pivots) < 2:
        return {"divergence": False, "reason": "顶分型不足"}
    i1, i2 = pivots[-2], pivots[-1]
    p1, p2 = float(highs.iloc[i1]), float(highs.iloc[i2])
    if p2 < p1 * 1.002:
        return {"divergence": False, "reason": "未创新高"}
    a1 = hist_area(hist, max(0, i1 - 8), i1)
    a2 = hist_area(hist, max(0, i2 - 8), i2)
    div = a2 < a1 * 0.85 and a1 > 0
    return {
        "divergence": div,
        "kind": "趋势背驰" if div else "无",
        "price1": round(p1, 3),
        "price2": round(p2, 3),
        "area1": round(a1, 4),
        "area2": round(a2, 4),
        "pivot_idx": (i1, i2),
    }
