"""分析报告补充数据：自动抓取 registry 指标，仅对真正失败项报缺口。"""
from __future__ import annotations

import os
import re
import time
from typing import Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DAILY_REPORT = os.path.join(SCRIPT_DIR, "..", "Wiki", "数据", "市场状态日报.md")

# 仅当 fetch 失败且无法从日报/Wiki 兜底时才写入缺口
_GAP_LABELS = {
    "minute_kline": "分钟级 K 线（做 T 精确时点）",
    "rs_vs_hs300": "相对强度 RS（相对沪深300，20日）",
    "northbound": "北向/南向资金净流入",
    "finance": "最新财务数据（ROE/营收/净利）",
}


def fetch_vipdoc_stats(code: str, *, lookback: int = 20) -> dict[str, Any]:
    try:
        from tdx_vipdoc import daily_vol_stats

        stats = daily_vol_stats(code, lookback=lookback)
        if stats:
            return stats
    except Exception as exc:
        return {"error": str(exc)}
    return {"error": "vipdoc 无本地日 K（检查 TDX_VIPDOC 路径）"}


def _parse_northbound_from_daily() -> dict[str, Any] | None:
    if not os.path.isfile(DAILY_REPORT):
        return None
    text = open(DAILY_REPORT, encoding="utf-8").read()
    m = re.search(r"北向净流入[^：:]*[：:]\s*([\d.]+)\s*亿元", text)
    s = re.search(r"南向[^：:]*[：:]\s*([\d.]+)\s*亿元", text)
    if not m:
        return None
    out: dict[str, Any] = {
        "north_net_yi": float(m.group(1)),
        "source": "市场状态日报",
    }
    if s:
        out["south_net_yi"] = float(s.group(1))
    upd = re.search(r"更新时间[：:]\s*([\d-]+\s+[\d:]+)", text)
    if upd:
        out["as_of"] = upd.group(1).strip()
    return out


def enrich_stock(code: str, *, name: str = "") -> dict[str, Any]:
    """抓取单标的报告所需的全部可自动获取数据。"""
    from fine_screen import get_finance_data
    from market_daily.supplement import fetch_minute_kline, fetch_northbound_snapshot, fetch_rs_vs_hs300

    code = str(code).zfill(6)
    out: dict[str, Any] = {"code": code, "name": name or code}

    fin = get_finance_data(code)
    out["finance"] = fin if fin else {"error": "财务接口无返回"}

    out["minute_kline"] = fetch_minute_kline(code)
    out["rs_vs_hs300"] = fetch_rs_vs_hs300(code)

    # 失败时重试一次（东方财富偶发空响应）
    if out["minute_kline"].get("error"):
        time.sleep(0.5)
        out["minute_kline"] = fetch_minute_kline(code)
    if out["rs_vs_hs300"].get("error"):
        time.sleep(0.5)
        out["rs_vs_hs300"] = fetch_rs_vs_hs300(code)

    nb = fetch_northbound_snapshot()
    if nb and nb.get("north_net_yi") is not None:
        out["northbound"] = {**nb, "source": "实时接口"}
    else:
        daily_nb = _parse_northbound_from_daily()
        if daily_nb:
            out["northbound"] = daily_nb
        else:
            out["northbound"] = {"error": "北向数据不可用"}

    out["vipdoc"] = fetch_vipdoc_stats(code)

    out["gaps"] = compute_gaps(out)
    return out


def compute_gaps(enrichment: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    for key, label in _GAP_LABELS.items():
        block = enrichment.get(key)
        if not block:
            gaps.append(label)
            continue
        if isinstance(block, dict) and block.get("error"):
            gaps.append(f"{label}（{block['error']}）")
    return gaps


def format_enrichment_markdown(enrichment: dict[str, Any]) -> str:
    """补充数据 Markdown（嵌入报告，替代「待补全」占位）。"""
    code = enrichment.get("code", "")
    name = enrichment.get("name", code)
    lines = [f"### 补充数据（{name} {code}）", ""]

    fin = enrichment.get("finance") or {}
    if fin and not fin.get("error"):
        lines.append(
            f"- **财务（最新一期）**：ROE {fin.get('roe')}% | 毛利率 {fin.get('gross_margin')}% | "
            f"净利率 {fin.get('net_margin')}% | 营收 {fin.get('revenue')} 亿 | 净利 {fin.get('net_profit')} 亿"
        )
    else:
        lines.append(f"- **财务**：{fin.get('error', '—')}")

    mk = enrichment.get("minute_kline") or {}
    if mk and not mk.get("error"):
        lines.append(
            f"- **5分钟K（近 {mk.get('bars_count')} 根）**：最新 {mk.get('last_time')} 收 **{mk.get('last_close')}** | "
            f"段内高/低 **{mk.get('session_high')} / {mk.get('session_low')}**（做 T 时点参考）"
        )
    else:
        lines.append(f"- **5分钟K**：{mk.get('error', '—')}")

    rs = enrichment.get("rs_vs_hs300") or {}
    if rs and not rs.get("error"):
        lines.append(
            f"- **RS vs 沪深300（{rs.get('days')}日）**：标的 {rs.get('stock_ret_pct'):+.1f}% vs 指数 "
            f"{rs.get('index_ret_pct'):+.1f}% → 利差 **{rs.get('rs_spread_pct'):+.1f}%**（{rs.get('label')}）"
        )
    else:
        lines.append(f"- **RS**：{rs.get('error', '—')}")

    nb = enrichment.get("northbound") or {}
    if nb and not nb.get("error"):
        src = nb.get("source", "接口")
        as_of = f"，截至 {nb['as_of']}" if nb.get("as_of") else ""
        south = f" | 南向 {nb['south_net_yi']} 亿" if nb.get("south_net_yi") is not None else ""
        lines.append(f"- **北向净流入**：{nb.get('north_net_yi')} 亿{south}（{src}{as_of}）")
    else:
        lines.append(f"- **北向**：{nb.get('error', '—')}")

    vd = enrichment.get("vipdoc") or {}
    if vd and not vd.get("error"):
        lines.append(
            f"- **vipdoc 本地日 K（近 {vd.get('lookback')} 日）**："
            f"σ **{vd.get('stdev_pct')}%** | 平均绝对涨跌 **{vd.get('mean_abs_pct')}%** | "
            f"最大单日 **{vd.get('max_abs_pct')}%**（1/3/7 日区间宽度与波动参考；路径 `{vd.get('path', '—')}`）"
        )
    else:
        lines.append(f"- **vipdoc 本地日 K**：{vd.get('error', '—')}")

    lines.append("")
    return "\n".join(lines)


def format_gaps_markdown(gaps: list[str]) -> str:
    if not gaps:
        return (
            "### 数据覆盖\n\n"
            "当前报告所需 **分钟K / RS / 北向 / 财务 / vipdoc** 均已自动抓取并写入上文；**无未登记数据缺口**。\n"
        )
    lines = ["### 数据缺口（待补全）", ""]
    for g in gaps:
        lines.append(f"- {g}")
    lines.append("")
    lines.append(
        "> 可经 `scripts/ai_sim/supplement_registry.yaml` 注册 fetcher，或由 Agent `data_requests` 申请启用。"
    )
    return "\n".join(lines)
