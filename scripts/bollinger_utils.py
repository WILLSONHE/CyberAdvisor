"""布林七轨 + 研判总结（fine_screen / ai_sim / sug 共用）。"""
from __future__ import annotations

import math
from typing import Any

try:
    from mootdx.quotes import Quotes
except ImportError:
    Quotes = None  # type: ignore

try:
    from stockstats import StockDataFrame
except ImportError:
    StockDataFrame = None  # type: ignore

_client = None


def get_quotes_client():
    global _client
    if _client is None and Quotes is not None:
        _client = Quotes.factory(market="std")
    return _client


def get_kline(code: str, days: int = 60, *, min_bars: int = 25):
    code = str(code).zfill(6)
    client = get_quotes_client()
    if client is not None:
        if code.startswith(("6", "9")) or code in ("000001", "000300", "000016", "000688", "000905"):
            market = 1
        else:
            market = 0
        try:
            k = client.bars(symbol=code, market=market, category=4, offset=days)
            if k is not None and len(k) >= min_bars:
                return k
        except Exception:
            pass
    try:
        from tdx_vipdoc import read_daily_bars

        df = read_daily_bars(code, limit=max(days, min_bars + 5))
        if df is not None and len(df) >= min_bars:
            return df.rename(columns={"vol": "volume"}) if "volume" not in df.columns else df
    except Exception:
        pass
    return None


def compute_bollinger_position(klines) -> dict[str, Any]:
    """七轨：顶(+3DEV)、二(+1)、中(20MA)、四(-1)、五(-2)、底(-3)。"""
    if klines is None or len(klines) < 25 or StockDataFrame is None:
        return {}
    try:
        df = klines.rename(columns={"vol": "volume"})
        sdf = StockDataFrame.retype(df)
        close = sdf["close"]
        std20 = close.rolling(20).std()
        dev = std20.rolling(5).mean().iloc[-1]
        mid_20 = close.rolling(20).mean().iloc[-1]
        price = close.iloc[-1]
        track4 = mid_20 - 1 * dev
        top_track = mid_20 + 3 * dev
        track2 = mid_20 + 1 * dev
        track5 = mid_20 - 2 * dev
        bot_track = mid_20 - 3 * dev
        bandwidth = (top_track - bot_track) / mid_20 if mid_20 else 0
        bw_series = (
            (close.rolling(20).mean() + 3 * std20.rolling(5).mean())
            - (close.rolling(20).mean() - 3 * std20.rolling(5).mean())
        ) / close.rolling(20).mean()
        bw_min_20 = bw_series.rolling(20).min().iloc[-1]
        is_converging = bandwidth <= bw_min_20 * 1.05
        if price >= top_track:
            zone = "顶轨以上"
        elif price >= track2:
            zone = "二轨~顶轨"
        elif price >= mid_20:
            zone = "中轨~二轨"
        elif price >= track4:
            zone = "四轨~中轨"
        elif price >= track5:
            zone = "五轨~四轨"
        else:
            zone = "底轨~五轨"
        recent_high = close.iloc[-10:].max()
        recent_low = close.iloc[-10:].min()
        had_surge = (recent_high / recent_low - 1) > 0.15 if recent_low > 0 else False
        at_track2 = abs(price - track2) / track2 < 0.03 if track2 else False
        n_pattern = had_surge and at_track2
        ma5 = close.rolling(5).mean().iloc[-1]
        ma20_slope = (
            (close.rolling(20).mean().iloc[-1] - close.rolling(20).mean().iloc[-5])
            / close.rolling(20).mean().iloc[-5]
            * 100
            if len(close) >= 25 and close.rolling(20).mean().iloc[-5]
            else 0
        )
        pct_vs_mid = (price / mid_20 - 1) * 100 if mid_20 else 0
        return {
            "price": round(float(price), 2),
            "mid": round(float(mid_20), 2),
            "track2": round(float(track2), 2),
            "track4": round(float(track4), 2),
            "track5": round(float(track5), 2),
            "top": round(float(top_track), 2),
            "bot": round(float(bot_track), 2),
            "zone": zone,
            "bandwidth_pct": round(bandwidth * 100, 1),
            "converging": bool(is_converging),
            "n_pattern": bool(n_pattern),
            "ma5": round(float(ma5), 2),
            "ma5_above_mid": bool(ma5 > mid_20),
            "ma20_slope_pct": round(float(ma20_slope), 2),
            "pct_vs_mid": round(float(pct_vs_mid), 2),
            "signal": (
                "破顶轨-离场"
                if price >= top_track
                else "N字二轨候选"
                if n_pattern
                else "收敛形态"
                if is_converging
                else "底轨附近-关注"
                if price <= track5
                else "正常"
            ),
        }
    except Exception as e:
        return {"error": str(e)}


def _kline_extra(klines) -> dict[str, Any]:
    if klines is None or len(klines) < 10:
        return {}
    try:
        c = klines["close"]
        v = klines["vol"]
        return {
            "ret_5d_pct": round((c.iloc[-1] / c.iloc[-6] - 1) * 100, 2) if len(c) >= 6 else None,
            "ret_20d_pct": round((c.iloc[-1] / c.iloc[-21] - 1) * 100, 2) if len(c) >= 21 else None,
            "vol_10d_avg": round(float(v.iloc[-10:].mean()), 0),
            "vol_ratio": round(float(v.iloc[-1] / v.iloc[-10:].mean()), 2)
            if float(v.iloc[-10:].mean()) > 0
            else None,
            "high_10d": round(float(c.iloc[-10:].max()), 2),
            "low_10d": round(float(c.iloc[-10:].min()), 2),
            "last10_closes": [round(float(x), 2) for x in c.iloc[-10:].tolist()],
        }
    except Exception:
        return {}


def bollinger_for_code(code: str, days: int = 60) -> dict[str, Any]:
    kl = get_kline(code, days)
    b = compute_bollinger_position(kl)
    if b and "error" not in b:
        b["code"] = code
        extra = _kline_extra(kl)
        if extra:
            b["kline_extra"] = extra
        try:
            from report_data import fetch_vipdoc_stats

            b["vipdoc"] = fetch_vipdoc_stats(code)
        except Exception:
            pass
    return b


def _price_level_label(b: dict[str, Any]) -> str:
    zone = b.get("zone", "")
    pct = b.get("pct_vs_mid", 0)
    if zone in ("顶轨以上", "二轨~顶轨"):
        return "相对偏高"
    if zone in ("底轨~五轨", "五轨~四轨"):
        return "相对偏低"
    if abs(pct) < 2:
        return "接近中枢"
    return "中性偏" + ("高" if pct > 0 else "低")


def _suitability(b: dict[str, Any]) -> tuple[list[str], list[str]]:
    ok: list[str] = []
    no: list[str] = []
    zone = b.get("zone", "")
    sig = b.get("signal", "")
    if b.get("converging"):
        no.append("带宽收敛，波动空间不足，不宜追涨杀跌")
    if zone in ("五轨~四轨", "底轨~五轨") or sig == "底轨附近-关注":
        ok.append("价位于通道中下段，可考虑分批低吸/做T进（需配合指数纪律）")
    if zone in ("二轨~顶轨", "顶轨以上") or sig == "破顶轨-离场":
        ok.append("价位于通道上段，持仓可考虑做T出或减仓")
        no.append("追高开新仓性价比低")
    if sig == "N字二轨候选":
        ok.append("N字回踩二轨附近，可观察是否出现二次上攻")
    if zone == "中轨~二轨":
        no.append("处于中轨~二轨，日内做T区间偏窄")
    return ok, no


def _position_pct_hint(b: dict[str, Any], *, has_position: bool) -> str:
    zone = b.get("zone", "")
    if zone in ("顶轨以上",):
        return "已持仓建议 ≤10% 组合权重或清仓观望；新开仓 0%"
    if zone in ("二轨~顶轨",):
        return "已持仓建议 ≤15%–20%；新开仓仅小仓试探（须指数允许）"
    if zone in ("中轨~二轨", "四轨~中轨"):
        return "已持仓建议 15%–25%；新开仓视指数纪律与标的池优先级"
    if zone in ("五轨~四轨", "底轨~五轨"):
        return "已持仓可持有或小幅加仓至 20%–25%；新开仓可相对积极（仍受 L1/L3 约束）"
    return "已持仓 10%–20%；新开仓视大盘与 Wiki 纪律"


def _pct_vs_price(price: float, level: float) -> float:
    if not price:
        return 0.0
    return round((level / price - 1) * 100, 2)


def _most_likely_level(probs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """倾向概率最高的挡位（同概率时取 |较现价| 较大者）。"""
    if not probs:
        return None
    return max(
        probs,
        key=lambda r: (
            float(r.get("prob_pct") or 0),
            abs(float(r.get("pct_vs_now") or 0)),
        ),
    )


def _nearest_level_to_target(
    probs: list[dict[str, Any]], target: float
) -> dict[str, Any] | None:
    if not probs:
        return None
    row = min(probs, key=lambda r: abs(float(r["price"]) - target))
    out = dict(row)
    mode = _most_likely_level(probs)
    if mode and float(mode["price"]) == float(out["price"]):
        out["pick_method"] = "mode"
    else:
        out["pick_method"] = "snap"
    return out


def _most_likely_for_horizon(
    probs: list[dict[str, Any]],
    *,
    price: float,
    prob_center: float,
    anchor: float,
    mid: float,
    b: dict[str, Any],
    days: int,
) -> dict[str, Any] | None:
    """1日=带内 mode；3日→锚点最近挡；7日→Wiki 均值回归目标（通道上下段→中轨）。"""
    if not probs:
        return None
    zone = b.get("zone", "")
    if days <= 1:
        out = _most_likely_level(probs)
        if out:
            out = dict(out)
            out["pick_method"] = "mode"
            out["pick_target"] = prob_center
        return out
    if days <= 3:
        target = anchor
        method = "anchor_snap"
    elif zone in ("五轨~四轨", "底轨~五轨", "四轨~中轨"):
        target = mid
        method = "mid_revert_7d"
    elif zone in ("二轨~顶轨", "顶轨以上", "中轨~二轨"):
        target = mid
        method = "mid_revert_7d"
    else:
        target = prob_center
        method = "center_snap"
    row = _nearest_level_to_target(probs, target)
    if not row:
        return None
    row = dict(row)
    row["pick_method"] = method
    row["pick_target"] = round(target, 2)
    return row


def _format_most_likely_line(ml: dict[str, Any] | None, *, horizon: str) -> str:
    if not ml:
        return f"**最有可能价位（{horizon}）**：数据不足"
    method = ml.get("pick_method") or "mode"
    method_note = {
        "mode": "1日带内概率最高挡",
        "anchor_snap": f"3日取离锚点 {ml.get('pick_target')} 最近挡",
        "mid_revert_7d": f"7日 Wiki 均值回归→中轨 {ml.get('pick_target')} 最近挡",
        "center_snap": f"取离概率中心 {ml.get('pick_target')} 最近挡",
        "snap": "取离回归目标最近挡",
    }.get(method, method)
    return (
        f"**最有可能价位（{horizon}）**：**{ml['price']}**"
        f"（{ml['label']}，较现价 {ml['pct_vs_now']:+.2f}%，表内概率 {ml['prob_pct']:.1f}%）"
        f" — {method_note}"
    )


def _dedupe_levels(levels: list[tuple[str, float]], *, min_gap_pct: float = 1.0) -> list[tuple[str, float]]:
    """按价格排序；仅合并无名称的邻近分位，保留七轨/区间边界/近端高低。"""
    if not levels:
        return []

    def _protected(label: str) -> bool:
        return any(k in label for k in ("轨", "近10", "区间下沿", "区间上沿"))

    sorted_lv = sorted(levels, key=lambda x: x[1])
    out: list[tuple[str, float]] = []
    for label, p in sorted_lv:
        if not out:
            out.append((label, round(float(p), 2)))
            continue
        prev_label, prev_p = out[-1]
        gap = abs(p / prev_p - 1) * 100 if prev_p else 999.0
        if gap < min_gap_pct and not _protected(label) and not _protected(prev_label):
            out[-1] = (f"{out[-1][0]}/{label}", round((out[-1][1] + p) / 2, 2))
        else:
            out.append((label, round(float(p), 2)))
    return out


def _levels_in_interval(
    b: dict[str, Any],
    lo: float,
    hi: float,
    ke: dict[str, Any],
    *,
    subdivide: int = 5,
) -> list[tuple[str, float]]:
    """收集 [lo, hi] 内的所有价格挡位（七轨 + 区间边界 + 近端高低 + 等分补充）。"""
    candidates: list[tuple[str, float]] = [
        ("区间下沿", lo),
        ("区间上沿", hi),
        ("底轨", b.get("bot")),
        ("五轨", b.get("track5")),
        ("四轨", b.get("track4")),
        ("中轨", b.get("mid")),
        ("二轨", b.get("track2")),
        ("顶轨", b.get("top")),
    ]
    if ke.get("high_10d") is not None:
        candidates.append(("近10日高", float(ke["high_10d"])))
    if ke.get("low_10d") is not None:
        candidates.append(("近10日低", float(ke["low_10d"])))

    in_range: list[tuple[str, float]] = []
    for label, p in candidates:
        if p is None:
            continue
        pf = float(p)
        if lo - 1e-6 <= pf <= hi + 1e-6:
            in_range.append((label, round(pf, 2)))

    in_range = _dedupe_levels(in_range, min_gap_pct=1.2)
    if len(in_range) < 3 and hi > lo:
        for i in range(subdivide):
            p = round(lo + (hi - lo) * i / max(subdivide - 1, 1), 2)
            in_range.append((f"区间{(i + 1) * 100 // subdivide}%分位", p))
        in_range = _dedupe_levels(in_range, min_gap_pct=0.8)
    return sorted(in_range, key=lambda x: x[1])


def _outlook_anchor(b: dict[str, Any], days: int, lo: float, hi: float) -> float:
    """技术倾向锚点价（非预测均值）。"""
    price = float(b.get("price") or lo)
    mid = float(b.get("mid") or price)
    track2 = float(b.get("track2") or mid)
    track4 = float(b.get("track4") or mid)
    slope = float(b.get("ma20_slope_pct") or 0)
    zone = b.get("zone", "")

    if days <= 3:
        if zone in ("顶轨以上", "二轨~顶轨"):
            anchor = 0.35 * price + 0.25 * mid + 0.40 * track2
        elif zone in ("底轨~五轨", "五轨~四轨"):
            anchor = 0.35 * price + 0.45 * mid + 0.20 * track4
        elif b.get("n_pattern"):
            anchor = 0.30 * price + 0.30 * mid + 0.40 * track2
        else:
            anchor = 0.40 * price + 0.45 * mid + 0.15 * track2
    else:
        reversion = 0.55 if abs(slope) < 1.5 else 0.45
        anchor = (1 - reversion) * price + reversion * mid
        if slope < -1:
            anchor = 0.35 * price + 0.45 * mid + 0.20 * track4
        elif slope > 1:
            anchor = 0.30 * price + 0.40 * mid + 0.30 * track2
    return max(lo, min(hi, round(anchor, 2)))


def _band_move(
    dev: float,
    days: int,
    params: dict[str, Any],
    *,
    price: float = 0,
    code: str = "",
) -> float:
    scale = float(params.get("band_days_scale") or 5)
    boll = dev * (days / scale) ** 0.5
    if params.get("use_realized_vol_floor", True) and price > 0 and code:
        try:
            from tdx_vipdoc import realized_daily_sigma_pct

            sig = realized_daily_sigma_pct(
                code, lookback=int(params.get("realized_vol_lookback", 20))
            )
            if sig:
                vol_move = (
                    price
                    * (sig / 100.0)
                    * (days ** 0.5)
                    * float(params.get("band_vol_scale") or 1.0)
                )
                return max(boll, vol_move)
        except Exception:
            pass
    return boll


def _sigma_param_keys(days: int) -> tuple[str, str]:
    if days <= 1:
        return "sigma_divisor_1d", "sigma_dev_floor_1d"
    if days <= 3:
        return "sigma_divisor_3d", "sigma_dev_floor_3d"
    return "sigma_divisor_7d", "sigma_dev_floor_7d"


def _outlook_sigma(dev: float, lo: float, hi: float, days: int, params: dict[str, Any]) -> float:
    """遗留：旧版概率 σ（calibrate 只读对照）；新概率层用 `_outlook_prob_sigma`。"""
    div_key, floor_key = _sigma_param_keys(days)
    div = float(params.get(div_key) or 2.8)
    floor = float(params.get(floor_key) or 0.35)
    return max((hi - lo) / div, dev * floor, 0.01)


def _outlook_prob_center(
    price: float,
    anchor: float,
    b: dict[str, Any],
    params: dict[str, Any],
    *,
    days: int = 1,
    lo: float | None = None,
    hi: float | None = None,
) -> float:
    """概率分布中心：vipdoc 现价基准 + 随 horizon 增强的 Wiki 均值回归（锚点/中轨）。"""
    mid = float(b.get("mid") or price)
    zone = b.get("zone", "")
    if zone in ("底轨~五轨", "五轨~四轨", "顶轨以上", "二轨~顶轨"):
        pw = float(params.get("prob_center_price_weight") or 0.55)
    else:
        pw = float(params.get("prob_center_price_weight_mid") or 0.65)
    pull = float(params.get("prob_horizon_reversion_pull") or 0.06) * max(0, days - 1)
    pw = max(0.12, pw - pull)
    mid_w = float(params.get("prob_mid_weight_per_day") or 0.035) * max(0, days - 1)
    mid_w = min(mid_w, 0.32)
    rem = max(0.0, 1.0 - pw - mid_w)
    center = pw * price + mid_w * mid + rem * anchor
    if lo is not None and hi is not None:
        center = max(lo, min(hi, center))
    return round(center, 2)


def _track_boost_for_horizon(params: dict[str, Any], days: int) -> float:
    base = float(params.get("track_level_boost") or 1.25)
    decay = float(params.get("prob_track_boost_decay_per_day") or 0.03)
    return max(1.05, base - decay * max(0, days - 1))


def _outlook_prob_sigma(
    lo: float,
    hi: float,
    params: dict[str, Any],
) -> float:
    """概率 spread σ：半带宽 × scale，使带内分布对齐 vipdoc 1σ 区间（约 68% 质量在带内）。"""
    half = (hi - lo) / 2.0
    scale = float(params.get("prob_sigma_halfband_scale") or 0.92)
    return max(half * scale, 0.01)


def export_outlook_horizon(
    b: dict[str, Any],
    *,
    days: int,
    kline_extra: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """导出可登记/复盘的 1日/3日/7日 预测快照（供 outlook_tracker）。"""
    from outlook_params import load_params

    params = params or load_params()
    ke = kline_extra or b.get("kline_extra") or {}
    price = float(b.get("price") or 0)
    mid = float(b.get("mid") or price)
    track2 = float(b.get("track2") or mid)
    dev = (track2 - mid) if track2 else 0
    move = _band_move(dev, days, params, price=price, code=str(b.get("code") or ""))
    lo, hi = round(price - move, 2), round(price + move, 2)
    lv = _levels_in_interval(b, lo, hi, ke)
    anchor = _outlook_anchor(b, days, lo, hi)
    prob_center = _outlook_prob_center(price, anchor, b, params, days=days, lo=lo, hi=hi)
    prob_sigma = _outlook_prob_sigma(lo, hi, params)
    boost = _track_boost_for_horizon(params, days)
    uni = float(params.get("prob_uniform_weight") or 0.06)
    probs = _level_probabilities(
        lv, anchor=prob_center, sigma=prob_sigma, b=b, track_boost=boost, uniform_weight=uni
    )
    top = _most_likely_for_horizon(
        probs, price=price, prob_center=prob_center, anchor=anchor, mid=mid, b=b, days=days
    )
    slope = float(b.get("ma20_slope_pct") or 0)
    zone = b.get("zone", "")
    if slope > 1 and b.get("ma5_above_mid"):
        bias = "偏多震荡"
    elif slope < -1 and not b.get("ma5_above_mid"):
        bias = "偏空震荡"
    elif zone in ("顶轨以上", "二轨~顶轨"):
        bias = "偏高回落风险"
    elif zone in ("底轨~五轨", "五轨~四轨"):
        bias = "偏低反弹机会"
    else:
        bias = "中枢震荡"
    return {
        "days": days,
        "lo": lo,
        "hi": hi,
        "lo_pct": _pct_vs_price(price, lo),
        "hi_pct": _pct_vs_price(price, hi),
        "anchor": anchor,
        "anchor_pct": _pct_vs_price(price, anchor),
        "prob_center": prob_center,
        "prob_center_pct": _pct_vs_price(price, prob_center),
        "bias": bias,
        "levels": [
            {"label": r["label"], "price": r["price"], "pct_vs_now": r["pct_vs_now"], "prob_pct": r["prob_pct"]}
            for r in probs
        ],
        "most_likely": top,
        "params_version": params.get("version"),
    }


def _level_probabilities(
    levels: list[tuple[str, float]],
    *,
    anchor: float,
    sigma: float,
    b: dict[str, Any],
    track_boost: float = 1.25,
    uniform_weight: float = 0.06,
) -> list[dict[str, Any]]:
    """vipdoc 带内高斯（中心=现价×权重+锚点×权重）+ 七轨加成 + 均匀底噪 → 倾向概率。"""
    if not levels or sigma <= 0:
        return []
    track_prices = {
        round(float(x), 2)
        for x in (
            b.get("bot"),
            b.get("track5"),
            b.get("track4"),
            b.get("mid"),
            b.get("track2"),
            b.get("top"),
        )
        if x is not None
    }
    uni = max(0.0, min(float(uniform_weight), 0.25))
    gauss_w = 1.0 - uni
    per_uni = uni / len(levels) if levels else 0.0
    weights: list[float] = []
    for _label, p in levels:
        w = gauss_w * math.exp(-0.5 * ((p - anchor) / sigma) ** 2)
        if round(p, 2) in track_prices:
            w *= track_boost
        w += per_uni
        weights.append(w)
    total = sum(weights) or 1.0
    price = float(b.get("price") or levels[0][1])
    rows: list[dict[str, Any]] = []
    for (label, p), w in zip(levels, weights):
        rows.append(
            {
                "label": label,
                "price": p,
                "pct_vs_now": _pct_vs_price(price, p),
                "prob_pct": round(w / total * 100, 1),
            }
        )
    drift = sum(r["prob_pct"] * r["pct_vs_now"] for r in rows) / 100
    for r in rows:
        r["drift_hint"] = drift
    return rows


def _format_prob_table(
    rows: list[dict[str, Any]],
    *,
    price: float,
    lo: float,
    hi: float,
    track_boost: float = 1.25,
    params_version: str | None = None,
    prob_sigma_scale: float = 0.92,
    prob_uniform_weight: float = 0.06,
) -> str:
    if not rows:
        return ""
    lo_pct = _pct_vs_price(price, lo)
    hi_pct = _pct_vs_price(price, hi)
    lines = [
        f"- **区间边界较现价**：下沿 {lo}（**{lo_pct:+.2f}%**）| 上沿 {hi}（**{hi_pct:+.2f}%**）",
        "",
        "| 挡位 | 价位 | 较现价 | 倾向概率 |",
        "|------|------|--------|----------|",
    ]
    for r in rows:
        lines.append(
            f"| {r['label']} | {r['price']} | {r['pct_vs_now']:+.2f}% | {r['prob_pct']:.1f}% |"
        )
    drift = rows[0].get("drift_hint") if rows else None
    if drift is not None:
        lines.append("")
        lines.append(
            f"- **概率加权较现价漂移**：**{float(drift):+.2f}%**"
            "（各挡位概率 × 较现价的加权平均；比「最高概率那一档」更能代表整体倾向位移）"
        )
    lines.append("")
    ver = params_version or "—"
    lines.append(
        f"> **倾向概率**：带内分布以 **现价×权重 + 技术锚点×权重** 为中心（vipdoc 1σ 区间 + Wiki 均值回归），"
        f"σ≈半带宽×{prob_sigma_scale:g}；"
        f"七轨挡位 ×{track_boost:g}；"
        f"含 {prob_uniform_weight * 100:.0f}% 均匀底噪避免边界概率过低。"
        "合计 100%；**非**盈利预测。"
        f" 参数版本 `{ver}`。"
    )
    return "\n".join(lines)


def _outlook_3d_7d(
    b: dict[str, Any], *, kline_extra: dict[str, Any] | None = None, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    """技术倾向（非保证预测）：结论 + 依据 + 区间挡位概率表。"""
    from outlook_params import load_params

    params = params or load_params()
    track_boost = float(params.get("track_level_boost") or 1.25)
    if not b or b.get("error"):
        return {
            "d1": "数据不足",
            "d3": "数据不足",
            "d7": "数据不足",
            "d1_detail": "",
            "d3_detail": "",
            "d7_detail": "",
            "note": "缺少足够日 K",
        }
    price = float(b.get("price") or 0)
    mid = float(b.get("mid") or price)
    track2 = float(b.get("track2") or mid)
    track4 = float(b.get("track4") or mid)
    top = float(b.get("top") or price)
    bot = float(b.get("bot") or price)
    dev = (track2 - mid) if track2 else 0
    slope = float(b.get("ma20_slope_pct") or 0)
    zone = b.get("zone", "")
    ke = kline_extra or {}

    def _band(days: int) -> tuple[float, float]:
        if not dev or not price:
            return (price, price)
        move = _band_move(dev, days, params, price=price, code=str(b.get("code") or ""))
        return (round(price - move, 2), round(price + move, 2))

    lo1, hi1 = _band(1)
    lo3, hi3 = _band(3)
    lo7, hi7 = _band(7)

    if slope > 1 and b.get("ma5_above_mid"):
        bias = "偏多震荡"
    elif slope < -1 and not b.get("ma5_above_mid"):
        bias = "偏空震荡"
    elif zone in ("顶轨以上", "二轨~顶轨"):
        bias = "偏高回落风险"
    elif zone in ("底轨~五轨", "五轨~四轨"):
        bias = "偏低反弹机会"
    else:
        bias = "中枢震荡"

    supports = [x for x in [track4, mid, ke.get("low_10d")] if x]
    resistances = [x for x in [track2, ke.get("high_10d"), top] if x]
    sup_str = " / ".join(f"{v:.2f}" for v in sorted(set(supports))[:3])
    res_str = " / ".join(f"{v:.2f}" for v in sorted(set(resistances), reverse=True)[:3])

    lv1 = _levels_in_interval(b, lo1, hi1, ke)
    lv3 = _levels_in_interval(b, lo3, hi3, ke)
    lv7 = _levels_in_interval(b, lo7, hi7, ke)
    anchor1 = _outlook_anchor(b, 1, lo1, hi1)
    anchor3 = _outlook_anchor(b, 3, lo3, hi3)
    anchor7 = _outlook_anchor(b, 7, lo7, hi7)
    pc1 = _outlook_prob_center(price, anchor1, b, params, days=1, lo=lo1, hi=hi1)
    pc3 = _outlook_prob_center(price, anchor3, b, params, days=3, lo=lo3, hi=hi3)
    pc7 = _outlook_prob_center(price, anchor7, b, params, days=7, lo=lo7, hi=hi7)
    boost = _track_boost_for_horizon(params, 1)
    uni = float(params.get("prob_uniform_weight") or 0.06)
    prob1 = _level_probabilities(
        lv1, anchor=pc1, sigma=_outlook_prob_sigma(lo1, hi1, params), b=b, track_boost=boost, uniform_weight=uni,
    )
    boost3 = _track_boost_for_horizon(params, 3)
    prob3 = _level_probabilities(
        lv3, anchor=pc3, sigma=_outlook_prob_sigma(lo3, hi3, params), b=b, track_boost=boost3, uniform_weight=uni,
    )
    boost7 = _track_boost_for_horizon(params, 7)
    prob7 = _level_probabilities(
        lv7, anchor=pc7, sigma=_outlook_prob_sigma(lo7, hi7, params), b=b, track_boost=boost7, uniform_weight=uni,
    )
    ml1 = _most_likely_for_horizon(prob1, price=price, prob_center=pc1, anchor=anchor1, mid=mid, b=b, days=1)
    ml3 = _most_likely_for_horizon(prob3, price=price, prob_center=pc3, anchor=anchor3, mid=mid, b=b, days=3)
    ml7 = _most_likely_for_horizon(prob7, price=price, prob_center=pc7, anchor=anchor7, mid=mid, b=b, days=7)
    track_boost = boost
    prob_sigma_scale = float(params.get("prob_sigma_halfband_scale") or 0.92)
    prob_uni = float(params.get("prob_uniform_weight") or 0.06)
    table1 = _format_prob_table(
        prob1, price=price, lo=lo1, hi=hi1, track_boost=track_boost,
        params_version=params.get("version"), prob_sigma_scale=prob_sigma_scale, prob_uniform_weight=prob_uni,
    )
    table3 = _format_prob_table(
        prob3, price=price, lo=lo3, hi=hi3, track_boost=track_boost,
        params_version=params.get("version"), prob_sigma_scale=prob_sigma_scale, prob_uniform_weight=prob_uni,
    )
    table7 = _format_prob_table(
        prob7, price=price, lo=lo7, hi=hi7, track_boost=track_boost,
        params_version=params.get("version"), prob_sigma_scale=prob_sigma_scale, prob_uniform_weight=prob_uni,
    )

    d1_lines = [
        f"**结论**：{bias}；下一交易日参考区间 **{lo1}–{hi1}**（下沿 {_pct_vs_price(price, lo1):+.2f}% / 上沿 {_pct_vs_price(price, hi1):+.2f}%）",
        _format_most_likely_line(ml1, horizon="1日"),
        f"**技术锚点价**：{anchor1}（较现价 {_pct_vs_price(price, anchor1):+.2f}%）",
        "**依据**：",
        f"- 通道：现价 {price} 位于 **{zone}**（距中轨 {b.get('pct_vs_mid', 0):+.1f}%）",
        f"- 均线：MA5 {b.get('ma5')} {'>' if b.get('ma5_above_mid') else '≤'} 中轨 {mid}",
    ]
    if ke.get("ret_5d_pct") is not None:
        d1_lines.append(f"- 动量：近5日 **{ke['ret_5d_pct']:+.1f}%**")
    if ke.get("vol_ratio") is not None:
        d1_lines.append(f"- 量能：最新日量/近10日均量 **{ke['vol_ratio']:.2f}**")
    d1_lines.append(f"- 近端支撑 **{sup_str}**；压力 **{res_str}**")
    d1_lines.append("")
    d1_lines.append("**区间内挡位倾向概率（1日）**：")
    d1_lines.append("")
    d1_lines.append(table1)

    d3_lines = [
        f"**结论**：{bias}；参考区间 **{lo3}–{hi3}**（下沿 {_pct_vs_price(price, lo3):+.2f}% / 上沿 {_pct_vs_price(price, hi3):+.2f}%）",
        _format_most_likely_line(ml3, horizon="3日"),
        f"**技术锚点价**：{anchor3}（较现价 {_pct_vs_price(price, anchor3):+.2f}%）",
        "**依据**：",
        f"- 通道：现价 {price} 位于 **{zone}**（距中轨 {b.get('pct_vs_mid', 0):+.1f}%）",
        f"- 均线：MA5 {b.get('ma5')} {'>' if b.get('ma5_above_mid') else '≤'} 中轨 {mid}；20MA 5日斜率 **{slope:+.2f}%**",
    ]
    if b.get("n_pattern"):
        d3_lines.append("- 形态：**N字二轨候选**（近10日振幅>15%，现价回踩二轨）")
    if ke.get("ret_5d_pct") is not None:
        d3_lines.append(f"- 动量：近5日 **{ke['ret_5d_pct']:+.1f}%**；近10日高/低 **{ke.get('high_10d')} / {ke.get('low_10d')}**")
    if ke.get("vol_ratio") is not None:
        d3_lines.append(f"- 量能：最新日量/近10日均量 **{ke['vol_ratio']:.2f}**")
    d3_lines.append(f"- 近端支撑 **{sup_str}**；压力 **{res_str}**")
    d3_lines.append("")
    d3_lines.append("**区间内挡位倾向概率（3日）**：")
    d3_lines.append("")
    d3_lines.append(table3)

    d7_lines = [
        f"**结论**：{bias}；参考区间 **{lo7}–{hi7}**（下沿 {_pct_vs_price(price, lo7):+.2f}% / 上沿 {_pct_vs_price(price, hi7):+.2f}%）",
        _format_most_likely_line(ml7, horizon="7日"),
        f"**技术锚点价**：{anchor7}（较现价 {_pct_vs_price(price, anchor7):+.2f}%）",
        "**依据**：",
        f"- 通道带宽 **{b.get('bandwidth_pct')}%**{'（收敛，波动收窄）' if b.get('converging') else '（未收敛，波动空间足）'}",
        f"- 七轨区间：底 {bot} ~ 顶 {top}；20MA 趋势斜率 **{slope:+.2f}%**",
    ]
    if ke.get("ret_20d_pct") is not None:
        d7_lines.append(f"- 中期：近20日 **{ke['ret_20d_pct']:+.1f}%**")
    if ke.get("last10_closes"):
        closes = ke["last10_closes"]
        d7_lines.append(f"- 近10日收盘序列：{' → '.join(str(c) for c in closes)}")
    d7_lines.append(
        f"- 情景：守 **中轨 {mid}** 则偏区间上沿测试二轨/前高；有效跌破则看向 **四轨 {track4}**"
    )
    d7_lines.append("")
    d7_lines.append("**区间内挡位倾向概率（7日）**：")
    d7_lines.append("")
    d7_lines.append(table7)

    def _ml_short(ml: dict[str, Any] | None) -> str:
        if not ml:
            return "—"
        return f"{ml['price']}（{ml['label']} {ml['pct_vs_now']:+.1f}%）"

    return {
        "d1": f"{bias}；最有可能 {_ml_short(ml1)}；{lo1}–{hi1}（{_pct_vs_price(price, lo1):+.1f}%～{_pct_vs_price(price, hi1):+.1f}%）",
        "d3": f"{bias}；最有可能 {_ml_short(ml3)}；{lo3}–{hi3}（{_pct_vs_price(price, lo3):+.1f}%～{_pct_vs_price(price, hi3):+.1f}%）",
        "d7": f"{bias}；最有可能 {_ml_short(ml7)}；{lo7}–{hi7}（{_pct_vs_price(price, lo7):+.1f}%～{_pct_vs_price(price, hi7):+.1f}%）",
        "d1_detail": "\n".join(d1_lines),
        "d3_detail": "\n".join(d3_lines),
        "d7_detail": "\n".join(d7_lines),
        "d1_prob": prob1,
        "d3_prob": prob3,
        "d7_prob": prob7,
        "d1_most_likely": ml1,
        "d3_most_likely": ml3,
        "d7_most_likely": ml7,
        "note": "vipdoc 1σ 区间 + Wiki 锚点偏移的带内倾向权重，非真实概率或盈利预测",
    }


def build_stock_verdict(
    code: str,
    *,
    name: str = "",
    has_position: bool = False,
    index_ok_buy: bool = True,
) -> dict[str, Any]:
    """单标的研判（供 sug / 模拟盘 / 报告总结）。"""
    b = bollinger_for_code(code)
    gaps: list[str] = []
    if not b or b.get("error"):
        gaps.append(f"{name or code}：日 K 不足 25 根或行情源失败")
        return {
            "name": name,
            "code": code,
            "ok": False,
            "gaps": gaps,
            "markdown": f"**{name or code}**：无法计算布林（需 mootdx 日 K）。",
        }

    level = _price_level_label(b)
    ok_list, no_list = _suitability(b)
    outlook = _outlook_3d_7d(b, kline_extra=b.get("kline_extra"))
    pos_hint = _position_pct_hint(b, has_position=has_position)

    if not index_ok_buy:
        no_list.append("指数纪律（如 4033 破线）禁止新开仓")
    can_open = index_ok_buy and b.get("zone") not in ("顶轨以上", "二轨~顶轨")
    hold_action = (
        "清仓/大幅减仓"
        if b.get("zone") == "顶轨以上"
        else "减仓或做T出"
        if b.get("zone") == "二轨~顶轨"
        else "持有"
        if has_position
        else "—"
    )

    md_lines = [
        f"### {name or code}（{code}）",
        f"- **现价 {b['price']}** | 位置：**{b['zone']}** | 相对20MA：**{level}**（{b['pct_vs_mid']:+.1f}%）",
        f"- 轨道：顶 {b['top']} / 二 {b['track2']} / 中 {b['mid']} / 四 {b['track4']} / 五 {b['track5']} / 底 {b['bot']}",
        f"- 信号：**{b['signal']}** | 带宽 {b['bandwidth_pct']}%{'（收敛）' if b.get('converging') else ''}",
        f"- **宜**：{'；'.join(ok_list) or '—'}",
        f"- **忌**：{'；'.join(no_list) or '—'}",
        f"- **建仓**：{'可试探' if can_open else '不宜'}（须叠加 Wiki 指数纪律）",
        f"- **持仓处置**：{hold_action} | 权重参考：{pos_hint}",
        f"- **1日倾向**：{outlook['d1']}",
        "",
        outlook.get("d1_detail", ""),
        "",
        f"- **3日倾向**：{outlook['d3']}",
        "",
        outlook.get("d3_detail", ""),
        "",
        f"- **7日倾向**：{outlook['d7']}",
        "",
        outlook.get("d7_detail", ""),
        "",
        f"- _{outlook['note']}_",
    ]
    return {
        "name": name,
        "code": code,
        "ok": True,
        "boll": b,
        "level": level,
        "can_open": can_open,
        "hold_action": hold_action,
        "position_hint": pos_hint,
        "outlook": outlook,
        "gaps": gaps,
        "markdown": "\n".join(md_lines),
        "score_buy": _sim_buy_score(b),
        "score_sell": _sim_sell_score(b),
    }


def _sim_buy_score(b: dict[str, Any]) -> float:
    zone = b.get("zone", "")
    scores = {
        "底轨~五轨": 1.0,
        "五轨~四轨": 0.85,
        "四轨~中轨": 0.55,
        "中轨~二轨": 0.35,
        "二轨~顶轨": 0.1,
        "顶轨以上": -0.5,
    }
    s = scores.get(zone, 0.3)
    if b.get("signal") == "N字二轨候选":
        s += 0.25
    if b.get("signal") == "收敛形态":
        s += 0.1
    if b.get("converging"):
        s -= 0.15
    return s


def _sim_sell_score(b: dict[str, Any]) -> float:
    zone = b.get("zone", "")
    if zone == "顶轨以上":
        return 1.0
    if zone == "二轨~顶轨":
        return 0.6
    if b.get("signal") == "破顶轨-离场":
        return 1.0
    if zone in ("底轨~五轨", "五轨~四轨"):
        return -0.3
    return 0.0


def build_report_summary_section(
    *,
    holdings: list[dict[str, Any]],
    candidates: list[dict[str, Any]] | None = None,
    sh_index: float | None = None,
    line_clear: float = 4033,
) -> str:
    """生成 sug / 分析报告用的「研判总结」Markdown 段。"""
    index_ok = sh_index is None or sh_index >= line_clear
    lines = [
        "## 研判总结",
        "",
        "> 解释报告内布林与仓位数据；1/3/7 日为**技术倾向**（非盈利预测）。",
        "",
    ]
    if sh_index is not None:
        lines.append(
            f"**大盘**：上证 {sh_index:.2f} vs 清仓线 {line_clear} → "
            f"{'指数允许考虑建仓' if index_ok else '指数纪律优先防守，新开仓原则上禁止'}。"
        )
        lines.append("")

    all_gaps: list[str] = []
    enrich_blocks: list[str] = []
    seen_codes: set[str] = set()

    def _append_stock(h: dict[str, Any], *, has_position: bool) -> None:
        c = str(h["code"]).zfill(6)
        v = build_stock_verdict(
            c,
            name=h.get("name", ""),
            has_position=has_position,
            index_ok_buy=index_ok,
        )
        lines.append(v["markdown"])
        lines.append("")
        all_gaps.extend(v.get("gaps", []))
        if c not in seen_codes:
            seen_codes.add(c)
            try:
                from report_data import enrich_stock, format_enrichment_markdown

                enr = enrich_stock(c, name=h.get("name", ""))
                enrich_blocks.append(format_enrichment_markdown(enr))
                all_gaps.extend(enr.get("gaps", []))
            except Exception as exc:
                all_gaps.append(f"{h.get('name', c)}：补充数据抓取异常（{exc}）")

    if holdings:
        lines.append("### 持仓标的")
        lines.append("")
        for h in holdings:
            _append_stock(h, has_position=True)

    if candidates:
        lines.append("### 关注/候选标的")
        lines.append("")
        for c in candidates[:5]:
            _append_stock(c, has_position=False)

    if enrich_blocks:
        lines.append("## 补充数据")
        lines.append("")
        lines.extend(enrich_blocks)

    try:
        from report_data import format_gaps_markdown

        merged = list(dict.fromkeys(all_gaps))
        lines.append(format_gaps_markdown(merged))
    except Exception:
        lines.append("### 数据缺口（待补全）")
        lines.append("")
        for g in dict.fromkeys(all_gaps):
            lines.append(f"- {g}")
    lines.append("")
    return "\n".join(lines)
