"""大盘/标的日内形态：高开低走、低开高走等；供做 T 文案与日报引用。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

DEFAULT_INDEX = "000001"
GAP_PCT = 0.003
PATH_PCT = 0.002
CHECKPOINT_TIME = "10:30"


@dataclass
class SessionPattern:
    trade_date: str
    prev_close: float | None
    open: float
    close: float
    high: float
    low: float
    gap_pct: float | None
    checkpoint_price: float
    pattern: str
    pattern_label: str
    zuot_bias: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "trade_date": self.trade_date,
            "prev_close": self.prev_close,
            "open": self.open,
            "close": self.close,
            "high": self.high,
            "low": self.low,
            "gap_pct": self.gap_pct,
            "checkpoint_price": self.checkpoint_price,
            "pattern": self.pattern,
            "pattern_label": self.pattern_label,
            "zuot_bias": self.zuot_bias,
        }


PATTERN_META: dict[str, tuple[str, str]] = {
    "high_open_low_close": ("高开低走", "早段冲高宜减、午后或尾盘再接"),
    "low_open_high_close": ("低开高走", "早段下探宜接、反弹段宜抛"),
    "high_open_high_close": ("高开高走", "强势延续，做 T 宜持为主、慎过早卖飞"),
    "low_open_low_close": ("低开低走", "弱势延续，做 T 宜观望或仅极小仓反弹抛"),
    "flat_up": ("平开高走", "震荡抬升，适合早买午抛"),
    "flat_down": ("平开低走", "震荡走弱，适合早卖午接"),
    "flat_choppy": ("震荡", "区间来回，按布林轨道做 T"),
}


def _split_by_day(df: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    if df is None or df.empty:
        return []
    work = df.copy()
    work["_day"] = work["time"].astype(str).str[:10]
    out: list[tuple[str, pd.DataFrame]] = []
    for day, grp in work.groupby("_day", sort=True):
        out.append((str(day), grp.drop(columns=["_day"]).reset_index(drop=True)))
    return out


def _checkpoint_price(day_bars: pd.DataFrame, checkpoint: str = CHECKPOINT_TIME) -> float:
    hh, mm = checkpoint.split(":")
    target = f" {int(hh):02d}:{int(mm):02d}"
    hits = day_bars[day_bars["time"].astype(str).str.endswith(target)]
    if not hits.empty:
        return float(hits.iloc[0]["close"])
    # 5 分钟线可能没有 10:30 精确 bar，取 >= checkpoint 的首根
    for _, row in day_bars.iterrows():
        t = str(row["time"])
        if len(t) >= 16 and t[11:16] >= target.strip():
            return float(row["close"])
    idx = min(len(day_bars) // 3, len(day_bars) - 1)
    return float(day_bars.iloc[max(idx, 0)]["close"])


def classify_session(
    day_bars: pd.DataFrame,
    prev_close: float | None,
    *,
    trade_date: str = "",
) -> SessionPattern:
    o = float(day_bars.iloc[0]["open"])
    c = float(day_bars.iloc[-1]["close"])
    hi = float(day_bars["high"].max())
    lo = float(day_bars["low"].min())
    cp = _checkpoint_price(day_bars)

    gap_pct: float | None = None
    if prev_close and prev_close > 0:
        gap_pct = round((o / prev_close - 1) * 100, 2)

    gap = gap_pct if gap_pct is not None else 0.0
    cp_vs_open = (cp / o - 1) if o > 0 else 0.0
    close_vs_open = (c / o - 1) if o > 0 else 0.0

    if gap >= GAP_PCT * 100:
        if cp_vs_open <= -PATH_PCT and close_vs_open < 0:
            key = "high_open_low_close"
        elif close_vs_open >= PATH_PCT:
            key = "high_open_high_close"
        else:
            key = "flat_choppy"
    elif gap <= -GAP_PCT * 100:
        if cp_vs_open >= PATH_PCT and close_vs_open > 0:
            key = "low_open_high_close"
        elif close_vs_open <= -PATH_PCT:
            key = "low_open_low_close"
        else:
            key = "flat_choppy"
    elif close_vs_open >= PATH_PCT:
        key = "flat_up"
    elif close_vs_open <= -PATH_PCT:
        key = "flat_down"
    else:
        key = "flat_choppy"

    label, bias = PATTERN_META[key]
    return SessionPattern(
        trade_date=trade_date or str(day_bars.iloc[0]["time"])[:10],
        prev_close=prev_close,
        open=round(o, 2),
        close=round(c, 2),
        high=round(hi, 2),
        low=round(lo, 2),
        gap_pct=gap_pct,
        checkpoint_price=round(cp, 2),
        pattern=key,
        pattern_label=label,
        zuot_bias=bias,
    )


def analyze_minute_bars(
    df: pd.DataFrame,
    *,
    daily_closes: dict[str, float] | None = None,
) -> list[SessionPattern]:
    """按交易日切分并逐日打形态标签。"""
    daily_closes = daily_closes or {}
    days = _split_by_day(df)
    patterns: list[SessionPattern] = []
    prev_close: float | None = None
    for day, bars in days:
        if daily_closes.get(day):
            prev_close = daily_closes[day]
        p = classify_session(bars, prev_close, trade_date=day)
        patterns.append(p)
        prev_close = p.close
    return patterns


def load_index_intraday(
    code: str = DEFAULT_INDEX,
    *,
    klt: int = 5,
    limit: int = 5000,
) -> pd.DataFrame | None:
    from tdx_market_data import read_minute_bars

    return read_minute_bars(code, klt=klt, limit=limit)


def _daily_prev_closes(code: str) -> dict[str, float]:
    from daily_bars import get_daily_bars

    df = get_daily_bars(code, limit=120, min_bars=30)
    if df is None or df.empty:
        return {}
    out: dict[str, float] = {}
    for i in range(1, len(df)):
        d = str(df.iloc[i]["datetime"])[:10]
        out[d] = float(df.iloc[i - 1]["close"])
    return out


def recent_index_patterns(
    code: str = DEFAULT_INDEX,
    *,
    klt: int = 5,
    days: int = 5,
) -> dict[str, Any]:
    df = load_index_intraday(code, klt=klt)
    if df is None or df.empty:
        return {"code": code, "error": "无本地分钟/5分钟K线"}

    prev_map = _daily_prev_closes(code)
    all_p = analyze_minute_bars(df, daily_closes=prev_map)
    recent = all_p[-days:] if days else all_p

    last = recent[-1] if recent else None
    transitions: dict[str, list[str]] = {}
    for i in range(len(all_p) - 1):
        nxt = all_p[i + 1].pattern_label
        transitions.setdefault(all_p[i].pattern_label, []).append(nxt)

    next_hint = _next_session_hint(last, transitions)

    return {
        "code": code,
        "klt": klt,
        "last_session": last.to_dict() if last else None,
        "recent_sessions": [p.to_dict() for p in recent],
        "next_session_hint": next_hint,
    }


def _next_session_hint(
    last: SessionPattern | None,
    transitions: dict[str, list[str]],
) -> dict[str, Any]:
    if not last:
        return {"summary": "数据不足", "zuot_note": ""}

    hist = transitions.get(last.pattern_label, [])
    if hist:
        from collections import Counter

        top = Counter(hist).most_common(2)
        follow = "、".join(f"{lbl}({cnt}次)" for lbl, cnt in top)
        stat_line = f"历史样本中「{last.pattern_label}」后一日常见：{follow}"
    else:
        stat_line = f"上一交易日为「{last.pattern_label}」，样本内无后继统计"

    gap_s = f"{last.gap_pct:+.2f}%" if last.gap_pct is not None else "—"
    summary = (
        f"{last.trade_date} 上证 {last.pattern_label}（开盘缺口 {gap_s}，"
        f"收 {last.close}）→ 次日关注：{last.zuot_bias}"
    )

    zuot_note = (
        f"**大盘参考**：{last.pattern_label}（{last.trade_date}，缺口{gap_s}）。"
        f"{last.zuot_bias}。{stat_line}"
    )
    return {
        "summary": summary,
        "zuot_note": zuot_note,
        "follow_patterns": hist,
        "last_pattern": last.pattern_label,
        "last_zuot_bias": last.zuot_bias,
    }


def format_market_zuot_header(code: str = DEFAULT_INDEX, *, klt: int = 5) -> str:
    """做 T 报告顶部：上一交易日形态 + 次日提示。"""
    info = recent_index_patterns(code, klt=klt, days=5)
    if info.get("error"):
        return f"\n## 大盘日内参考\n\n> {info['error']}\n"

    hint = info.get("next_session_hint") or {}
    last = info.get("last_session") or {}
    lines = [
        "\n## 大盘日内参考（上证指数）\n",
        f"> {hint.get('summary', '')}\n",
        "",
        "| 日期 | 形态 | 缺口% | 收 | 做T倾向 |",
        "|------|------|-------|-----|---------|",
    ]
    for s in info.get("recent_sessions") or []:
        gap = s.get("gap_pct")
        gap_s = f"{gap:+.2f}" if gap is not None else "—"
        lines.append(
            f"| {s.get('trade_date', '')} | {s.get('pattern_label', '')} | "
            f"{gap_s} | {s.get('close', '')} | {s.get('zuot_bias', '')} |"
        )
    lines.append("")
    if last:
        lines.append(
            f"**下一交易日开盘关注**：{hint.get('last_zuot_bias', '')}；"
            f"9:31 确认缺口方向，10:30 对照前一日同类形态。"
        )
    lines.append("")
    lines.append("")
    try:
        from chan.analyze import analyze_index
        from chan.report import format_chan_brief

        lines.append(f"> **缠论·上证**：{format_chan_brief(analyze_index())}\n")
    except Exception:
        pass
    return "\n".join(lines)


def zuot_timing_note(code: str = DEFAULT_INDEX, *, klt: int = 5) -> str:
    """单标的做 T 块内追加一行大盘节奏提示。"""
    info = recent_index_patterns(code, klt=klt, days=3)
    hint = info.get("next_session_hint") or {}
    note = hint.get("zuot_note")
    return f"- {note}\n" if note else ""


def classify_today_live(code: str = DEFAULT_INDEX, *, klt: int = 1) -> dict[str, Any] | None:
    """盘中/收盘后：用最新一日分钟线实时打标（供日报 supplement）。"""
    df = load_index_intraday(code, klt=klt, limit=300)
    if df is None or df.empty:
        return None
    days = _split_by_day(df)
    if not days:
        return None
    day, bars = days[-1]
    prev_map = _daily_prev_closes(code)
    # 前一交易日收
    prev_close = prev_map.get(day)
    if prev_close is None and len(days) >= 2:
        prev_close = float(days[-2][1].iloc[-1]["close"])
    p = classify_session(bars, prev_close, trade_date=day)
    return p.to_dict()
