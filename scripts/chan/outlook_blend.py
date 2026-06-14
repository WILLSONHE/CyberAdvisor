"""缠论 × 1/3/7 日 outlook 概率模型融合（ZD/ZG/保护位/买卖点）。"""
from __future__ import annotations

from typing import Any


def load_chan_snapshot(code: str, *, has_position: bool = False) -> dict[str, Any] | None:
    try:
        from chan.analyze import analyze_code

        snap = analyze_code(str(code).zfill(6), has_position=has_position)
        return snap if snap.get("ok") else None
    except Exception:
        return None


def _f(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def structural_anchor(chan: dict[str, Any], *, price: float, mid: float) -> float:
    """缠论结构锚：用于概率中心与 3/7 日回归目标。"""
    zd = _f(chan.get("ZD"))
    zg = _f(chan.get("ZG"))
    protect = _f(chan.get("protect_price"))
    hint = str(chan.get("buy_point") or "")
    if "三买" in hint and zg > 0:
        return round(zg * 0.998 + price * 0.002, 2)
    if "二买" in hint or "一买" in hint:
        base = protect if protect > 0 else zd
        if base > 0 and mid > 0:
            return round(0.55 * base + 0.45 * mid, 2)
        return base or mid or price
    if "卖" in hint or "观望" in hint:
        if zd > 0:
            return round(zd, 2)
        return protect or mid or price
    if zd > 0 and zg > 0:
        return round((zd + zg) / 2, 2)
    return mid or price


def adjust_band(
    price: float,
    lo: float,
    hi: float,
    chan: dict[str, Any],
    params: dict[str, Any],
    *,
    days: int,
) -> tuple[float, float, str]:
    """约束预测区间：保护位作下沿、卖点压缩上沿、买点略扩上沿。"""
    notes: list[str] = []
    protect = _f(chan.get("protect_price"))
    hint = str(chan.get("buy_point") or "")
    action = str(chan.get("action") or "")

    if params.get("chan_band_floor_protect", True) and protect > 0:
        new_lo = max(lo, protect)
        if new_lo > lo + 1e-6:
            notes.append(f"下沿抬至保护位 {protect}")
        lo = new_lo

    if "卖" in hint or action == "sell":
        shrink = float(params.get("chan_sell_hi_shrink") or 0.65)
        hi = round(price + max(0.0, hi - price) * shrink, 2)
        notes.append(f"顶背驰/卖点→上沿×{shrink:g}")

    if any(k in hint for k in ("一买", "二买", "三买")) and days >= 3:
        expand = float(params.get("chan_buy_hi_expand") or 1.06)
        cap = float(params.get("chan_buy_hi_expand_cap") or 1.12)
        expand = min(expand + 0.01 * max(0, days - 3), cap)
        hi = round(price + (hi - price) * expand, 2)
        notes.append(f"买点结构→上沿×{expand:.2f}")

    if lo > hi:
        hi = round(lo + max(price * 0.005, 0.01), 2)

    note = "；".join(notes) if notes else ""
    return lo, hi, note


def blend_prob_center(
    price: float,
    center: float,
    struct_anchor: float,
    chan: dict[str, Any],
    params: dict[str, Any],
    *,
    days: int,
    lo: float,
    hi: float,
) -> float:
    pull = float(params.get("chan_center_pull") or 0.18)
    pull += float(params.get("chan_center_pull_per_day") or 0.025) * max(0, days - 1)
    pull = min(pull, 0.42)
    out = (1.0 - pull) * center + pull * struct_anchor

    hint = str(chan.get("buy_point") or "")
    action = str(chan.get("action") or "")
    if any(k in hint for k in ("一买", "二买", "三买")):
        skew = float(params.get("chan_buy_center_skew") or 0.012) * days
        out += price * skew
    elif "卖" in hint or action == "sell":
        skew = float(params.get("chan_sell_center_skew") or 0.015) * days
        out -= price * skew

    return round(max(lo, min(hi, out)), 2)


def extra_levels(chan: dict[str, Any], lo: float, hi: float) -> list[tuple[str, float]]:
    rows: list[tuple[str, float]] = []
    for label, key in (
        ("中枢下沿ZD", "ZD"),
        ("中枢上沿ZG", "ZG"),
        ("缠论保护位", "protect_price"),
    ):
        p = _f(chan.get(key))
        if p > 0 and lo - 1e-6 <= p <= hi + 1e-6:
            rows.append((label, round(p, 2)))
    return rows


def boost_prices(chan: dict[str, Any]) -> dict[float, float]:
    """价位 → 额外概率权重乘数。"""
    out: dict[float, float] = {}
    for key in ("ZD", "ZG", "protect_price"):
        p = round(_f(chan.get(key)), 2)
        if p > 0:
            out[p] = 1.0
    return out


def apply_level_boost(
    price_key: float,
    base_boost: float,
    chan_boost_map: dict[float, float],
    params: dict[str, Any],
) -> float:
    mult = float(params.get("chan_level_boost") or 1.35)
    tol = float(params.get("chan_level_match_pct") or 0.8) / 100.0
    pk = round(price_key, 2)
    for cp, _ in chan_boost_map.items():
        if cp <= 0:
            continue
        if abs(pk - cp) / cp <= tol:
            return base_boost * mult
    return base_boost


def bias_overlay(boll_bias: str, chan: dict[str, Any]) -> str:
    hint = str(chan.get("buy_point") or "—")
    trend = str(chan.get("trend_day") or "")
    zd = chan.get("ZD")
    zg = chan.get("ZG")
    addon = f"缠论 {hint}（{trend}；ZD≈{zd} ZG≈{zg}）"
    if "买" in hint:
        return f"{boll_bias}；{addon}→结构偏多"
    if "卖" in hint or "观望" in hint:
        return f"{boll_bias}；{addon}→结构偏空/观望"
    return f"{boll_bias}；{addon}"


def pick_target_with_chan(
    *,
    days: int,
    zone: str,
    anchor: float,
    prob_center: float,
    mid: float,
    chan: dict[str, Any],
    price: float,
) -> tuple[float, str]:
    """7/3 日最有可能价：缠论结构目标优先于纯布林回归。"""
    struct = structural_anchor(chan, price=price, mid=mid)
    hint = str(chan.get("buy_point") or "")
    if days <= 3:
        if any(k in hint for k in ("二买", "三买")) and struct > price:
            return struct, "chan_struct_3d"
        return anchor, "anchor_snap"
    if "三买" in hint and struct >= price:
        return struct, "chan_zg_7d"
    if "卖" in hint or str(chan.get("action")) == "sell":
        zd = _f(chan.get("ZD"))
        if zd > 0:
            return zd, "chan_zd_7d"
    if zone in ("五轨~四轨", "底轨~五轨", "四轨~中轨"):
        return mid, "mid_revert_7d"
    if zone in ("二轨~顶轨", "顶轨以上", "中轨~二轨"):
        return mid, "mid_revert_7d"
    return prob_center, "center_snap"


def format_chan_outlook_note(chan: dict[str, Any], band_note: str) -> str:
    parts = [
        f"**缠论结构**：{chan.get('buy_point')} | {chan.get('structure')} | 保护 **{chan.get('protect_price')}**",
    ]
    if band_note:
        parts.append(f"区间调整：{band_note}")
    return "；".join(parts)


def blend_horizon(
    *,
    price: float,
    lo: float,
    hi: float,
    anchor: float,
    prob_center: float,
    bias: str,
    b: dict[str, Any],
    params: dict[str, Any],
    days: int,
    chan: dict[str, Any] | None,
) -> dict[str, Any]:
    """单 horizon 缠论融合；无 chan 时原样返回。"""
    if not chan or not params.get("chan_blend_enabled", True):
        return {
            "lo": lo,
            "hi": hi,
            "anchor": anchor,
            "prob_center": prob_center,
            "bias": bias,
            "extra_levels": [],
            "chan_boost_map": {},
            "chan_note": "",
            "chan": None,
        }
    mid = _f(b.get("mid"), price)
    lo2, hi2, band_note = adjust_band(price, lo, hi, chan, params, days=days)
    struct = structural_anchor(chan, price=price, mid=mid)
    anchor2 = round((1.0 - 0.12) * anchor + 0.12 * struct, 2)
    anchor2 = max(lo2, min(hi2, anchor2))
    pc2 = blend_prob_center(price, prob_center, struct, chan, params, days=days, lo=lo2, hi=hi2)
    bias2 = bias_overlay(bias, chan)
    return {
        "lo": lo2,
        "hi": hi2,
        "anchor": anchor2,
        "prob_center": pc2,
        "bias": bias2,
        "extra_levels": extra_levels(chan, lo2, hi2),
        "chan_boost_map": boost_prices(chan),
        "chan_note": format_chan_outlook_note(chan, band_note),
        "chan": chan,
        "struct_anchor": struct,
    }
