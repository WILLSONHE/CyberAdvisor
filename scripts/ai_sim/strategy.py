"""AI 模拟盘交易决策（规则引擎，4033 软约束）。"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime

from ai_sim.config import (
    LINE_CLEAR,
    LINE_FULL,
    MAX_POSITIONS,
    MAX_WEIGHT,
    TOTAL_CASH,
)
from ai_sim.portfolio_ops import active_positions, buy_by_amount, cash_available, equity_ratio, sell_all
from ai_sim.runtime_params import get as param
from ai_sim.universe import UniverseEntry, build_universe
from sim_portfolio import _norm_code


@dataclass
class Decision:
    action: str  # buy | sell | hold | rebalance
    name: str
    code: str
    reason_kind: str  # 止损 | 止盈 | 风控降仓 | 涨幅榜买入 | 追踪买入
    reason: str
    style: str = "短线"
    amount: float = 0.0


_SOURCE_LABEL = {
    "daily_gain": "市场状态日报·涨幅板块成分",
    "track": "博主标的追踪（活跃）",
}


def _sell_reason_kind(pnl_pct: float) -> tuple[str, str]:
    stop = param("STOP_LOSS_PCT")
    take = param("TAKE_PROFIT_PCT")
    if pnl_pct <= stop:
        return (
            "止损",
            f"浮亏 {pnl_pct:.1f}% 触及止损线 {stop:g}%",
        )
    if pnl_pct >= take:
        return (
            "止盈",
            f"浮盈 {pnl_pct:.1f}% 触及止盈线 {take:g}%",
        )
    return ("风控降仓", "")


def _buy_reason(e: UniverseEntry, target_ratio: float, current_ratio: float, regime: str, *, rebound: bool = False) -> tuple[str, str]:
    src = _SOURCE_LABEL.get(e.source, e.source)
    kind = "修复建仓" if rebound else ("涨幅榜买入" if e.source == "daily_gain" else "追踪买入")
    detail = (
        f"{regime}；当前仓位 {current_ratio:.0%} 低于目标 {target_ratio:.0%}，"
        f"从{src}选股{'（Agent 判定大盘即将修复/上涨）' if rebound else '建仓'}"
    )
    return kind, detail


def _sh_index(tick_path: str) -> float | None:
    if not os.path.isfile(tick_path):
        return None
    data = json.loads(open(tick_path, encoding="utf-8").read())
    for q in data.get("indices", []):
        if q.get("code") == "000001" or q.get("name") == "上证指数":
            return float(q.get("close", 0))
    return None


def _stock_map(tick_path: str) -> dict[str, dict]:
    if not os.path.isfile(tick_path):
        return {}
    data = json.loads(open(tick_path, encoding="utf-8").read())
    out: dict[str, dict] = {}
    for s in data.get("stocks", []):
        out[_norm_code(s["code"])] = s
    return out


def _target_equity_ratio(sh_close: float | None) -> tuple[float, str]:
    if sh_close is None:
        return param("EQUITY_TARGET_NORMAL"), "指数缺失，按默认仓位"
    if sh_close < LINE_CLEAR:
        return (
            param("EQUITY_TARGET_BELOW_CLEAR"),
            f"上证 {sh_close:.2f} < {LINE_CLEAR}（4033 软约束降仓）",
        )
    if sh_close >= LINE_FULL:
        return min(0.85, param("EQUITY_TARGET_NORMAL") + 0.1), f"上证 {sh_close:.2f} ≥ {LINE_FULL}（可偏高仓位）"
    return param("EQUITY_TARGET_NORMAL"), f"上证 {sh_close:.2f} 在 {LINE_CLEAR}–{LINE_FULL} 区间"


def _hold_days(row) -> int:
    today = date.today()
    try:
        open_d = datetime.strptime(str(row.get("建仓日期", today))[:10], "%Y-%m-%d").date()
    except ValueError:
        open_d = today
    return max(0, (today - open_d).days)


@dataclass
class TradePlan:
    decisions: list[Decision]
    regime: str
    target_ratio: float
    current_ratio: float
    buy_skip: str = ""
    tick_note: str = ""
    quotes: dict[str, dict] = field(default_factory=dict)


def plan_trades(tick_path: str, *, agent: dict | None = None) -> TradePlan:
    from ai_sim.runtime_params import reload

    reload()
    universe = build_universe()
    quotes = _stock_map(tick_path)
    sh = _sh_index(tick_path)
    target_ratio, regime = _target_equity_ratio(sh)
    current_ratio = equity_ratio()
    pos = active_positions()
    held = {str(r["标的"]).strip(): _norm_code(r["代码"]) for _, r in pos.iterrows()}
    decisions: list[Decision] = []
    buy_skip = ""
    tick_note = "每 15 分钟采集行情；仅在有明确信号时成交，默认观望"
    rebound = (agent or {}).get("rebound_buy") or (agent or {}).get("dip_buy") or {}
    rebound_signal = bool(agent and agent.get("ok") and rebound.get("signal"))
    rebound_allowed = rebound_signal

    # 卖出：止损 / 止盈 / 超配降仓（建仓当日不降仓）
    rebalance_slots = 0
    for _, row in pos.iterrows():
        name = str(row["标的"]).strip()
        code = _norm_code(row.get("代码"))
        cost = float(row["成本"] or 0)
        q = quotes.get(code, {})
        price = q.get("price") or float(row.get("现价") or cost)
        if cost <= 0:
            continue
        pnl_pct = (price - cost) / cost * 100
        if pnl_pct <= param("STOP_LOSS_PCT"):
            kind, detail = _sell_reason_kind(pnl_pct)
            decisions.append(Decision("sell", name, code, kind, detail, "短线"))
        elif pnl_pct >= param("TAKE_PROFIT_PCT"):
            kind, detail = _sell_reason_kind(pnl_pct)
            decisions.append(Decision("sell", name, code, kind, detail, "短线"))
        elif current_ratio > target_ratio + 0.05:
            if _hold_days(row) < param("REBALANCE_MIN_HOLD_DAYS"):
                continue
            if rebalance_slots >= 1:
                continue
            kind = "风控降仓"
            detail = (
                f"{regime}；目标仓位 {target_ratio:.0%}，"
                f"当前 {current_ratio:.0%} 超配 {current_ratio - target_ratio:.0%}，"
                f"减持 1 只至接近目标（非清仓）"
            )
            decisions.append(Decision("sell", name, code, kind, detail, "风控"))
            rebalance_slots += 1

    # 买入：4033 下默认禁买；Agent 判定「中长期低点/即将修复」时可例外
    blocked_below_clear = param("NO_BUY_BELOW_CLEAR") and sh is not None and sh < LINE_CLEAR
    if blocked_below_clear and not rebound_allowed:
        parts = [f"上证 {sh:.2f} < {LINE_CLEAR}，4033 软约束下不开新仓"]
        if not rebound_signal:
            parts.append(
                "需 Agent `rebound_buy.signal=true`（判断大盘处于中长期低点且即将修复/上涨）方可试探建仓"
            )
        elif not agent or not agent.get("ok"):
            parts.append("Agent 未成功分析，无法发出修复建仓信号")
        else:
            parts.append("Agent 未给出修复建仓信号")
        buy_skip = "；".join(parts) + "（本 tick 仅观察）"
    elif len(held) >= MAX_POSITIONS:
        buy_skip = f"已达最大持仓 {MAX_POSITIONS} 只，不再新开仓"
    elif current_ratio >= target_ratio - param("BUY_MIN_GAP"):
        buy_skip = (
            f"当前仓位 {current_ratio:.0%} 与目标 {target_ratio:.0%} 差距不足 "
            f"{param('BUY_MIN_GAP'):.0%}，无需买入"
        )
    else:
        cash = cash_available()
        totals_mkt = sum(float(r.get("市值") or 0) for _, r in pos.iterrows())
        budget_left = max(0.0, target_ratio * TOTAL_CASH - totals_mkt)
        slots_left = max(1, MAX_POSITIONS - len(held))
        slot = min(MAX_WEIGHT * TOTAL_CASH, cash, budget_left / slots_left)

        candidates: list[tuple[float, UniverseEntry]] = []
        for e in universe:
            if e.name in held or e.code in held.values():
                continue
            if e.source not in ("track", "daily_gain"):
                continue
            q = quotes.get(_norm_code(e.code), {})
            price = q.get("price")
            if price is None:
                continue
            score = 1.0 if e.source == "daily_gain" else 0.5
            if e.source == "track":
                score += 0.3
            chg = q.get("change_pct")
            if chg is not None and float(chg) < 0 and not rebound_allowed:
                continue
            if rebound_allowed and chg is not None and float(chg) < 0:
                score += 0.2
            candidates.append((score, e))

        if rebound_allowed:
            tick_note += "；Agent 判定大盘即将修复/上涨，允许破线环境下试探建仓"
        max_buys = param("MAX_BUYS_PER_TICK")
        if rebound_allowed and max_buys < 1:
            max_buys = 1
        candidates.sort(key=lambda x: -x[0])
        if not candidates:
            buy_skip = "标的池无满足条件的候选（需 tick 有报价；修复建仓允许当日下跌标的），跳过买入"
        elif slot < param("MIN_TRADE_YUAN") or budget_left < param("MIN_TRADE_YUAN"):
            buy_skip = f"可用预算 {budget_left:,.0f} 元低于最小成交额 {param('MIN_TRADE_YUAN'):,.0f} 元"
        else:
            for _, e in candidates[:max_buys]:
                if slot < param("MIN_TRADE_YUAN") or budget_left < param("MIN_TRADE_YUAN"):
                    break
                style = "短线" if e.source == "daily_gain" else "波段"
                amt = min(slot, budget_left)
                kind, detail = _buy_reason(e, target_ratio, current_ratio, regime, rebound=rebound_allowed)
                decisions.append(
                    Decision(
                        "buy",
                        e.name,
                        e.code,
                        kind,
                        detail,
                        style,
                        amt,
                    )
                )
                budget_left -= amt

    if not decisions and not buy_skip:
        buy_skip = "无明确交易信号，保持现状"

    sells = [d for d in decisions if d.action == "sell"]
    buys = [d for d in decisions if d.action == "buy"]
    return TradePlan(
        decisions=sells + buys,
        regime=regime,
        target_ratio=target_ratio,
        current_ratio=current_ratio,
        buy_skip=buy_skip,
        tick_note=tick_note,
        quotes=quotes,
    )


def execute_decisions(decisions: list[Decision], *, tick_quotes: dict[str, dict] | None = None) -> list[dict]:
    results: list[dict] = []
    ordered = [d for d in decisions if d.action == "sell"] + [d for d in decisions if d.action == "buy"]
    for d in ordered:
        if d.action == "sell":
            r = sell_all(d.name, reason=d.reason, tick_quotes=tick_quotes)
            if r:
                r["style"] = d.style
                r["reason_kind"] = d.reason_kind
                r["reason"] = d.reason
                results.append(r)
        elif d.action == "buy" and d.amount > 0:
            r = buy_by_amount(d.name, d.code, d.amount, style=d.style)
            if r:
                r["reason_kind"] = d.reason_kind
                r["reason"] = d.reason
                results.append(r)
    return results
