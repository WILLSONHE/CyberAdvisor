"""中长期市场上下文：多日指数/成交额/60 分钟 K 线/北向/隔夜 — 供 Agent 判修复。"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from ai_sim.config import TICK_ROOT
from ai_sim.index_session import _sh_from_tick_data, format_session_for_prompt, session_index_stats
from market_daily.history_store import load_daily_history

_INDEX_CODES = (
    ("000001", "上证指数"),
    ("399001", "深证成指"),
    ("399006", "创业板指"),
)

_DAY_CLOSE_PREF = ("1515", "1500", "1445", "1430", "1145", "1130")


def _index_from_tick_data(data: dict, code: str) -> dict | None:
    for q in data.get("indices", []):
        c = str(q.get("code", "")).zfill(6)
        if c == code or (code == "000001" and q.get("name") == "上证指数"):
            close = float(q.get("close") or 0)
            if close <= 0:
                return None
            return {
                "close": close,
                "low": float(q.get("low") or close),
                "high": float(q.get("high") or close),
                "open": float(q.get("open") or close),
                "change_pct": q.get("change_pct"),
                "turnover_yi": q.get("turnover_yi"),
            }
    return None


def _day_indices_from_tick(day_dir: str) -> dict[str, dict] | None:
    if not os.path.isdir(day_dir):
        return None
    files = {f.replace(".json", ""): os.path.join(day_dir, f) for f in os.listdir(day_dir) if f.endswith(".json")}
    if not files:
        return None
    path = None
    for label in _DAY_CLOSE_PREF:
        if label in files:
            path = files[label]
            break
    if not path:
        path = files[max(files)]
    try:
        data = json.loads(open(path, encoding="utf-8").read())
    except (OSError, json.JSONDecodeError):
        return None
    out: dict[str, dict] = {}
    for code, _ in _INDEX_CODES:
        row = _index_from_tick_data(data, code)
        if row:
            out[code] = row
    return out or None


def _merge_history_and_ticks(*, days: int = 10) -> list[dict[str, Any]]:
    """优先 JSON 历史摘要，tick 归档补全/回填。"""
    by_date: dict[str, dict] = {}
    for row in load_daily_history(days=days):
        date = row.get("date")
        if date:
            by_date[date] = {"date": date, "indices": dict(row.get("indices") or {}), "northbound": row.get("northbound") or {}}

    if os.path.isdir(TICK_ROOT):
        day_names = sorted(
            d for d in os.listdir(TICK_ROOT) if len(d) == 10 and d[4] == "-" and d[7] == "-"
        )
        for day in day_names[-days:]:
            tick_idx = _day_indices_from_tick(os.path.join(TICK_ROOT, day))
            if not tick_idx:
                continue
            slot = by_date.setdefault(day, {"date": day, "indices": {}, "northbound": {}})
            for code, row in tick_idx.items():
                slot["indices"].setdefault(code, {}).update(row)

    return [by_date[k] for k in sorted(by_date.keys())][-days:]


def load_tick_supplement(tick_path: str) -> dict[str, Any]:
    if not tick_path or not os.path.isfile(tick_path):
        return {}
    try:
        data = json.loads(open(tick_path, encoding="utf-8").read())
    except (OSError, json.JSONDecodeError):
        return {}
    return data.get("supplement") or {}


def format_kline_60m_section(kline_60m: dict[str, Any]) -> list[str]:
    lines = ["### 60 分钟 K 线（L3 底部结构）", ""]
    if not kline_60m:
        lines.append("（未采集）")
        return lines
    for code, _name in _INDEX_CODES:
        block = kline_60m.get(code) or {}
        bars = block.get("bars") or []
        if not bars:
            continue
        lines.append(f"**{block.get('name', _name)}**（最近 {len(bars)} 根）：")
        lines.append("")
        lines.append("| 时间 | 开 | 收 | 高 | 低 |")
        lines.append("|------|-----|-----|-----|-----|")
        for b in bars[-8:]:
            lines.append(
                f"| {b.get('time','')} | {b['open']:.2f} | {b['close']:.2f} | {b['high']:.2f} | {b['low']:.2f} |"
            )
        lines.append("")
    return lines


def format_turnover_section(history: list[dict]) -> list[str]:
    lines = ["### 成交额趋势（L5 缩量，亿元）", ""]
    if not history:
        lines.append("（尚无历史摘要）")
        return lines
    lines.append("| 日期 | 上证 | 深成指 | 创业板 |")
    lines.append("|------|------|--------|--------|")
    for row in history[-10:]:
        idx = row.get("indices") or {}
        def _t(c: str) -> str:
            v = (idx.get(c) or {}).get("turnover_yi")
            return f"{v:.2f}" if v is not None else "—"

        lines.append(f"| {row['date']} | {_t('000001')} | {_t('399001')} | {_t('399006')} |")
    lines.append("")
    return lines


def format_multi_index_section(history: list[dict]) -> list[str]:
    lines = [
        "### 关键点位（L1/L3/L4 · Wiki 参考，非规则引擎硬编码）",
    ]
    sh_cur = None
    if history:
        sh_cur = (history[-1].get("indices") or {}).get("000001", {}).get("close")
    if sh_cur:
        lines.append(
            f"- L1（Wiki）：见 [[指数纪律框架]] — 常见 **4033** / **4130** | 上证现价 **{sh_cur:.2f}**（距 Wiki L1 4033 {sh_cur - 4033:+.2f} 点，**供你判断，非引擎门禁**）"
        )
    else:
        lines.append("- L1：**4033** / **4130**")
    lines.extend(
        [
            "- L3：**4120 站稳** 或 **60 分钟及以上明确底部**",
            "- L4：**4000** → 破则 **3950**",
            "",
            "### 近 N 日主要指数收盘",
            "",
            "| 日期 | 上证 | 深成指 | 创业板 |",
            "|------|------|--------|--------|",
        ]
    )
    for row in history[-10:]:
        idx = row.get("indices") or {}

        def _c(code: str) -> str:
            v = (idx.get(code) or {}).get("close")
            ch = (idx.get(code) or {}).get("change_pct")
            if v is None:
                return "—"
            if ch is not None:
                return f"{v:.2f} ({ch:+.2f}%)"
            return f"{v:.2f}"

        lines.append(f"| {row['date']} | {_c('000001')} | {_c('399001')} | {_c('399006')} |")
    lines.append("")
    return lines


def format_northbound_section(supplement: dict, history: list[dict]) -> list[str]:
    lines = ["### 北向 / 南向资金（当日 + 近史）", ""]
    nb = supplement.get("northbound") or {}
    if nb:
        lines.append(
            f"- **北向净流入**：{nb.get('north_net_yi', '—')} 亿元 | "
            f"**南向**：{nb.get('south_net_yi', '—')} 亿元"
        )
        hgt = nb.get("hgt") or {}
        sgt = nb.get("sgt") or {}
        if hgt or sgt:
            lines.append(
                f"- 沪股通 {hgt.get('net_yi', '—')} 亿 | 深股通 {sgt.get('net_yi', '—')} 亿"
            )
    else:
        lines.append("- 当日快照：（未采集）")
    hist_nb = [h.get("northbound") for h in history if h.get("northbound")]
    if hist_nb:
        lines.append("")
        lines.append("| 日期 | 北向(亿) | 来源 |")
        lines.append("|------|---------|------|")
        for row in history[-8:]:
            n = row.get("northbound") or {}
            val = n.get("north_net_yi")
            if val is None:
                continue
            lines.append(f"| {row['date']} | {val} | {row.get('source', '—')} |")
    lines.append("")
    return lines


def format_optional_metrics_section(supplement: dict[str, Any]) -> list[str]:
    lines = ["### 扩展宏观指标（Agent 启用）", ""]
    found = False
    for key in ("us_vix", "us_10y_yield"):
        row = supplement.get(key)
        if not row or not isinstance(row, dict) or row.get("error"):
            continue
        found = True
        ch = row.get("change_pct")
        chs = f" ({ch:+.2f}%)" if isinstance(ch, (int, float)) else ""
        lines.append(f"- **{row.get('name', key)}**：{row.get('close', '—')}{chs}")
    if not found:
        lines.append("（本 tick 未启用；可通过 data_requests enable registry 指标）")
    lines.append("")
    return lines


def format_overnight_section(overnight: list[dict]) -> list[str]:
    lines = ["### 隔夜外盘（修复/风险外溢）", ""]
    if not overnight:
        lines.append("（本 tick 未采集；见 09:15/09:30 tick 或 Wiki 日更）")
        return lines
    lines.append("| 市场 | 收盘 | 涨跌幅 | 更新时间 |")
    lines.append("|------|------|--------|----------|")
    for q in overnight:
        lines.append(
            f"| {q.get('name','')} | {q.get('close', 0):.2f} | {q.get('change_pct', 0):+.2f}% | {q.get('update_time','')} |"
        )
    lines.append("")
    lines.append("> 费城半导体以 **SOXX ETF** 代理；A50 期货不可用，以 **恒生国企** 作参考。")
    lines.append("")
    return lines


def format_full_market_context(tick_path: str, *, days: int = 10) -> str:
    """Agent 用完整补充上下文。"""
    history = _merge_history_and_ticks(days=days)
    supplement = load_tick_supplement(tick_path)
    if not supplement.get("kline_60m"):
        try:
            from ai_sim.supplement_registry import build_supplement_payload
            from ai_sim.supplement_state import enabled_metrics

            include_overnight = (tick_path and "0915" in tick_path.replace("\\", "/")) or (
                tick_path and "0930" in tick_path.replace("\\", "/")
            )
            supplement = {
                **supplement,
                **build_supplement_payload(
                    enabled_metrics(),
                    include_overnight=include_overnight,
                    kline_limit=20,
                ),
            }
        except Exception:
            pass
    session_txt = format_session_for_prompt(session_index_stats(tick_path))

    parts: list[str] = [
        "## 中长期市场上下文（判修复/上涨）",
    ]
    try:
        from chan.analyze import analyze_index
        from chan.report import format_chan_markdown

        parts.append("")
        parts.append("## 缠论·上证（第一优先级）")
        parts.append(format_chan_markdown(analyze_index()).strip())
    except Exception as exc:
        parts.append(f"（缠论上下文失败：{exc}）")
    parts.extend([
        "",
        *format_multi_index_section(history),
        *format_turnover_section(history),
    ])
    if supplement.get("kline_60m"):
        parts.extend(format_kline_60m_section(supplement["kline_60m"]))
    else:
        parts.extend(["### 60 分钟 K 线", "", "（tick 无 supplement，请读 Wiki 日更）", ""])
    parts.extend(format_northbound_section(supplement, history))
    parts.extend(format_overnight_section(supplement.get("overnight") or []))
    parts.extend(format_optional_metrics_section(supplement))
    parts.extend(
        [
            "### 今日 tick 序列（辅助，非建仓时点依据）",
            "",
            session_txt,
            "",
            "> **rebound_buy**：综合上表判断 **中长期调整低点 + 即将修复/上涨**；须看 L3 60min 结构、L5 缩量、北向与外盘。",
        ]
    )
    return "\n".join(parts)


# 兼容旧调用
def recent_index_context(*, days: int = 10) -> dict:
    history = _merge_history_and_ticks(days=days)
    sh_rows = []
    for row in history:
        sh = (row.get("indices") or {}).get("000001")
        if not sh:
            continue
        sh_rows.append(
            {
                "date": row["date"],
                "close": sh["close"],
                "low": sh.get("low", sh["close"]),
                "high": sh.get("high", sh["close"]),
            }
        )
    if not sh_rows:
        return {"days": [], "swing_low": None, "swing_high": None, "current": None}
    lows = [r["low"] for r in sh_rows]
    highs = [r["high"] for r in sh_rows]
    return {
        "days": sh_rows,
        "swing_low": min(lows),
        "swing_high": max(highs),
        "current": sh_rows[-1]["close"],
    }


def format_index_context_for_prompt(ctx: dict) -> str:
    """Deprecated：请用 format_full_market_context。"""
    if not ctx.get("days"):
        return "（尚无多日数据）"
    cur = ctx["current"]
    lines = [
        f"上证现价 {cur:.2f}；近 {len(ctx['days'])} 日区间 {ctx['swing_low']:.2f}–{ctx['swing_high']:.2f}",
    ]
    return "\n".join(lines)
