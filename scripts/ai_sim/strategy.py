"""AI 自主模拟盘交易决策（执行层：Agent 读 Wiki 后的 param + buy_permission；无指数/布林硬编码门禁）。"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime

from ai_sim.config import (
    MAX_POSITIONS,
    MAX_WEIGHT,
    TOTAL_CASH,
)
from ai_sim.portfolio_ops import active_positions, buy_by_amount, cash_available, equity_ratio, sell_all
from ai_sim.runtime_params import get as param
from ai_sim.universe import UniverseEntry, build_universe
from bollinger_utils import _sim_buy_score, bollinger_for_code
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
    "track": "标的追踪（活跃）",
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


def _buy_reason(e: UniverseEntry, target_ratio: float, current_ratio: float, regime: str) -> tuple[str, str]:
    src = _SOURCE_LABEL.get(e.source, e.source)
    kind = "涨幅榜买入" if e.source == "daily_gain" else "追踪买入"
    detail = (
        f"{regime}；当前仓位 {current_ratio:.0%} 低于目标 {target_ratio:.0%}，"
        f"Agent 已允许开新仓，从{src}按综合得分选股"
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
    target = param("EQUITY_TARGET_NORMAL")
    if sh_close is None:
        return target, "指数缺失；目标仓位取自 Agent/默认参数"
    return target, f"上证 {sh_close:.2f}；目标股票仓位 {target:.0%}（Agent 据 Wiki 调参）"


def _agent_buy_allowed(agent: dict | None) -> bool:
    if not agent or not agent.get("ok"):
        return False
    perm = agent.get("buy_permission")
    if isinstance(perm, dict) and "allowed" in perm:
        return bool(perm.get("allowed"))
    rebound = agent.get("rebound_buy") or agent.get("dip_buy") or {}
    return bool(rebound.get("signal"))


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


def _boll_from_quote(code: str, q: dict) -> dict:
    if q.get("boll_zone"):
        return {
            "zone": q.get("boll_zone"),
            "signal": q.get("boll_signal"),
            "mid": q.get("boll_mid"),
            "track2": q.get("boll_track2"),
            "track4": q.get("boll_track4"),
            "track5": q.get("boll_track5"),
            "top": q.get("boll_top"),
            "bot": q.get("boll_bot"),
        }
    b = bollinger_for_code(code)
    if b and "error" not in b:
        return b
    return {}


def _index_chan(tick_path: str) -> dict:
    if not os.path.isfile(tick_path):
        return {}
    try:
        data = json.loads(open(tick_path, encoding="utf-8").read())
        ic = data.get("index_chan")
        if ic and ic.get("ok"):
            return ic
    except Exception:
        pass
    try:
        from chan.analyze import analyze_index
        from chan.policy import compact_chan

        return compact_chan(analyze_index())
    except Exception:
        return {}


def plan_trades(tick_path: str, *, agent: dict | None = None) -> TradePlan:
    from ai_sim.runtime_params import reload

    reload()
    universe = build_universe()
    quotes = _stock_map(tick_path)
    index_chan = _index_chan(tick_path)
    sh = _sh_index(tick_path)
    target_ratio, regime = _target_equity_ratio(sh)
    current_ratio = equity_ratio()
    pos = active_positions()
    held = {str(r["标的"]).strip(): _norm_code(r["代码"]) for _, r in pos.iterrows()}
    decisions: list[Decision] = []
    buy_skip = ""
    tick_note = "缠论第一优先级：指数+标的 chan 门禁 → Agent buy_permission → 布林/outlook 仅排序"

    agent_ok = bool(agent and agent.get("ok"))
    agent_buy = _agent_buy_allowed(agent)
    chan_block = bool(index_chan.get("ok") and index_chan.get("action") == "sell")

    if chan_block:
        buy_skip = f"指数缠论 {index_chan.get('buy_point')}，禁止新开仓（优先于 Agent）"
    elif not agent_ok:
        buy_skip = "Agent 未成功分析，默认不开新仓（须读 Wiki 后 buy_permission.allowed=true）"
    elif not agent_buy:
        buy_skip = (
            "Agent 未允许开新仓（buy_permission.allowed=false）；"
            "须同时满足缠论买点与 Wiki 指数纪律"
        )

    blocked = chan_block or not agent_ok or not agent_buy

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
        vip = q.get("vipdoc") or {}
        chan = q.get("chan") or {}
        vip_note = f"；vipdoc σ {vip['stdev_pct']}%" if vip.get("stdev_pct") is not None else ""
        if chan.get("buy_point"):
            vip_note += f"；缠论 {chan.get('structure')} | {chan.get('buy_point')} | 动作={chan.get('action')}"
        ol = q.get("outlook_1d") or {}
        if ol.get("price"):
            vip_note += f"；1日最有可能价 {ol['price']}"
        from chan.policy import should_force_sell

        force, freason = should_force_sell(chan if chan.get("ok") else None, price=price)
        if force:
            decisions.append(
                Decision(
                    "sell",
                    name,
                    code,
                    "缠论减仓",
                    f"{freason}" + vip_note,
                    "缠论",
                )
            )
            continue
        if pnl_pct <= param("STOP_LOSS_PCT"):
            kind, detail = _sell_reason_kind(pnl_pct)
            decisions.append(Decision("sell", name, code, kind, detail + vip_note, "短线"))
        elif pnl_pct >= param("TAKE_PROFIT_PCT"):
            kind, detail = _sell_reason_kind(pnl_pct)
            decisions.append(Decision("sell", name, code, kind, detail + vip_note, "短线"))
        elif current_ratio > target_ratio + 0.05:
            if _hold_days(row) < param("REBALANCE_MIN_HOLD_DAYS"):
                continue
            if rebalance_slots >= 1:
                continue
            detail = (
                f"{regime}；目标仓位 {target_ratio:.0%}，"
                f"当前 {current_ratio:.0%} 超配 {current_ratio - target_ratio:.0%}，"
                f"减持 1 只至接近目标（非清仓）"
            )
            decisions.append(Decision("sell", name, code, "风控降仓", detail, "风控"))
            rebalance_slots += 1

    if blocked:
        pass
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

        candidates: list[tuple[float, UniverseEntry, str]] = []
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
            if chg is not None:
                score += max(-0.3, min(0.3, float(chg) / 20.0))
            boll_note = ""
            boll = _boll_from_quote(_norm_code(e.code), q)
            chan = q.get("chan") or {}
            from chan.policy import allows_new_buy, score_for_ranking

            ok_buy, chan_reason = allows_new_buy(chan, index_chan)
            if not ok_buy:
                continue
            if chan:
                score += score_for_ranking(chan) * 2.5
                boll_note = f"；缠论 {chan.get('structure')} | {chan.get('buy_point')}（{chan_reason}）"
            if boll:
                score += _sim_buy_score(boll) * 0.25
                boll_note += f"；布林 {boll.get('zone')}（{boll.get('signal')}）"
            vip = q.get("vipdoc") or {}
            if vip.get("stdev_pct") is not None:
                boll_note += f"；vipdoc σ {vip['stdev_pct']}%"
                if float(vip["stdev_pct"]) > 5:
                    score -= 0.08
            ol1 = q.get("outlook_1d")
            if ol1 and ol1.get("price"):
                boll_note += f"；1日最有可能价 {ol1['price']}"
            candidates.append((score, e, boll_note))

        if agent_buy:
            tick_note += "；Agent 已允许开新仓"
        max_buys = param("MAX_BUYS_PER_TICK")
        candidates.sort(key=lambda x: -x[0])
        if not candidates:
            buy_skip = "标的池无缠论合格买点（或 tick 无报价），跳过买入"
        elif slot < param("MIN_TRADE_YUAN") or budget_left < param("MIN_TRADE_YUAN"):
            buy_skip = f"可用预算 {budget_left:,.0f} 元低于最小成交额 {param('MIN_TRADE_YUAN'):,.0f} 元"
        elif max_buys < 1:
            buy_skip = f"Agent 参数 MAX_BUYS_PER_TICK={max_buys}，本 tick 不新开仓"
        else:
            for _, e, boll_note in candidates[:max_buys]:
                if slot < param("MIN_TRADE_YUAN") or budget_left < param("MIN_TRADE_YUAN"):
                    break
                style = "短线" if e.source == "daily_gain" else "波段"
                amt = min(slot, budget_left)
                kind, detail = _buy_reason(e, target_ratio, current_ratio, regime)
                if boll_note:
                    detail += boll_note
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
