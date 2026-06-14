"""预测偏差 ≥1% 时的详细原因分析（大盘/个股/公告/模型）。"""
from __future__ import annotations

import os
import re
import sys
from datetime import date, datetime, timedelta
from typing import Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

GAP_THRESHOLD_PCT = 1.0
GAP_DECIMALS = 4

_INDEX_CODES = (
    ("000001", "上证指数"),
    ("399001", "深证成指"),
    ("399006", "创业板指"),
    ("000300", "沪深300"),
)

_WIKI_ROOT = os.path.join(SCRIPT_DIR, "..", "Wiki")
_RAW_ROOT = os.path.join(SCRIPT_DIR, "..", "Raw")
_DAILY_REPORT = os.path.join(_WIKI_ROOT, "数据", "市场状态日报.md")


def _parse_date(s: str) -> date | None:
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _closes_in_window(code: str, start: date, end: date) -> list[tuple[date, float]]:
    from daily_bars import get_daily_bars

    df = get_daily_bars(code, limit=90, min_bars=20)
    if df is None or df.empty:
        return []
    out: list[tuple[date, float]] = []
    for i in range(len(df)):
        ds = str(df.iloc[i].get("datetime") or df.iloc[i].get("date") or "")[:10]
        d = _parse_date(ds)
        if not d or d < start or d > end:
            continue
        out.append((d, float(df.iloc[i]["close"])))
    return sorted(out, key=lambda x: x[0])


def _window_return_pct(code: str, start: date, end: date) -> float | None:
    bars = _closes_in_window(code, start, end)
    if len(bars) < 2:
        pre = _closes_in_window(code, start - timedelta(days=10), start)
        if pre:
            bars = [pre[-1]] + bars
    if len(bars) < 2:
        return None
    base = bars[0][1]
    if base <= 0:
        return None
    return round((bars[-1][1] / base - 1) * 100, GAP_DECIMALS)


def _fetch_announcements(code: str, start: date, end: date, *, limit: int = 3) -> list[str]:
    """东方财富公告摘要（预测窗口内）。"""
    try:
        import requests

        session = requests.Session()
        session.trust_env = False
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://data.eastmoney.com/notices/stock/",
            }
        )
        params = {
            "sr": -1,
            "page_size": limit,
            "page_index": 1,
            "ann_type": "A",
            "client_source": "web",
            "stock_list": str(code).zfill(6),
            "f_node": 0,
            "s_node": 0,
        }
        r = session.get(
            "https://np-anotice-stock.eastmoney.com/api/security/announcement/getAnnouncementList",
            params=params,
            timeout=15,
        )
        r.raise_for_status()
        items = (r.json().get("data") or {}).get("list") or []
        out: list[str] = []
        for it in items:
            title = (it.get("title") or "").strip()
            ann_date = (it.get("notice_date") or it.get("display_time") or "")[:10]
            if not title:
                continue
            ad = _parse_date(ann_date)
            if ad and (ad < start or ad > end):
                continue
            short = title[:48] + ("…" if len(title) > 48 else "")
            out.append(f"{ann_date} {short}")
        return out[:limit]
    except Exception:
        return []


def _scan_local_mentions(name: str, code: str, start: date, end: date) -> list[str]:
    """Wiki / Raw 中窗口期内的相关提及。"""
    hits: list[str] = []
    keywords = [name, code]
    if len(name) >= 2:
        keywords.append(name[:2])
    date_patterns = []
    d = start
    while d <= end:
        date_patterns.append(d.strftime("%Y-%m-%d"))
        date_patterns.append(f"{d.month}月{d.day}日")
        d += timedelta(days=1)

    for root, label in ((_WIKI_ROOT, "Wiki"), (_RAW_ROOT, "Raw")):
        if not os.path.isdir(root):
            continue
        for dirpath, _, files in os.walk(root):
            for fn in files:
                if not fn.endswith((".md", ".txt")):
                    continue
                path = os.path.join(dirpath, fn)
                try:
                    text = open(path, encoding="utf-8", errors="ignore").read(12000)
                except OSError:
                    continue
                if not any(k in text for k in keywords if k):
                    continue
                if not any(p in text for p in date_patterns):
                    if name not in text and code not in text:
                        continue
                rel = os.path.relpath(path, root).replace("\\", "/")[:60]
                hits.append(f"{label}/{rel}")
                if len(hits) >= 2:
                    return hits
    return hits


def _northbound_note(track_from: date, due_date: date) -> str:
    if not os.path.isfile(_DAILY_REPORT):
        return ""
    text = open(_DAILY_REPORT, encoding="utf-8").read()
    m = re.search(r"北向净流入[^：:\n]*[：:]\s*([-\d.]+)\s*亿元", text)
    if not m:
        return ""
    nb = float(m.group(1))
    if abs(nb) >= 30:
        direction = "大幅净流入" if nb > 0 else "大幅净流出"
        return f"近期北向{direction}{abs(nb):.0f}亿，或影响大盘风险偏好"
    return ""


def build_deviation_reason(
    *,
    code: str,
    name: str,
    track_from: date,
    due_date: date,
    pred_price: float,
    actual: float,
    gap_pct: float,
    h: dict[str, Any],
    rev: dict[str, Any] | None = None,
) -> str:
    """|差距%| ≥ 1 返回详细原因；否则空字符串。"""
    if abs(gap_pct) < GAP_THRESHOLD_PCT:
        return ""

    rev = rev or {}
    parts: list[str] = []
    direction = "高于" if gap_pct > 0 else "低于"
    parts.append(
        f"实际{actual:.2f}{direction}预测{pred_price:.2f}，偏差{gap_pct:+.{GAP_DECIMALS}f}%"
    )

    stk_ret = _window_return_pct(code, track_from, due_date)
    idx_notes: list[str] = []
    for idx_code, idx_name in _INDEX_CODES:
        ir = _window_return_pct(idx_code, track_from, due_date)
        if ir is not None:
            idx_notes.append(f"{idx_name}{ir:+.{GAP_DECIMALS}f}%")
    if idx_notes:
        parts.append("窗口大盘：" + "、".join(idx_notes))
    if stk_ret is not None:
        parts.append(f"个股窗口涨跌{stk_ret:+.{GAP_DECIMALS}f}%")
        sh_ret = _window_return_pct("000001", track_from, due_date)
        if sh_ret is not None:
            spread = round(stk_ret - sh_ret, GAP_DECIMALS)
            if abs(spread) >= 0.5:
                if spread > 0:
                    parts.append(
                        f"较上证多涨{spread:.{GAP_DECIMALS}f}pct，主题/资金偏好强于模型假设"
                    )
                else:
                    parts.append(
                        f"较上证少涨{abs(spread):.{GAP_DECIMALS}f}pct，独立走弱或利好兑现"
                    )

    lo, hi = float(h.get("lo") or 0), float(h.get("hi") or 0)
    bias = str(h.get("bias") or "")
    if rev.get("in_band_close"):
        parts.append(f"收盘仍在区间{lo}–{hi}内，但偏离最有可能价；倾向标签「{bias}」权重可能不匹配")
    elif actual > hi:
        parts.append(f"收盘{actual:.2f}突破预测上沿{hi:.2f}，区间偏窄或未计入突发利好")
    elif actual < lo:
        parts.append(f"收盘{actual:.2f}跌破预测下沿{lo:.2f}，区间偏窄或未计入突发利空")
    else:
        parts.append(f"倾向「{bias}」与走势不一致")

    nb = _northbound_note(track_from, due_date)
    if nb:
        parts.append(nb)

    try:
        from market_daily.supplement import fetch_rs_vs_hs300

        rs = fetch_rs_vs_hs300(code, days=20)
        if rs.get("rs_pct") is not None:
            parts.append(f"20日RS较沪深300 {rs['rs_pct']:+.2f}%")
    except Exception:
        pass

    anns = _fetch_announcements(code, track_from, due_date)
    if anns:
        parts.append("公告：" + "；".join(anns))

    mentions = _scan_local_mentions(name, code, track_from, due_date)
    if mentions:
        parts.append("本地材料提及：" + "、".join(mentions))

    if abs(gap_pct) >= 2.0:
        if gap_pct > 0:
            parts.append("校准建议：下回可上修锚点权重或加宽 band_vol_scale")
        else:
            parts.append("校准建议：下回可下修锚点或加宽区间以覆盖尾部波动")

    return "。".join(parts)
