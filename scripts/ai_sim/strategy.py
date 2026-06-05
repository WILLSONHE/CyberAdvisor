"""AI 模拟盘交易决策（规则引擎，4033 软约束）。"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from ai_sim.config import (
    EQUITY_TARGET_BELOW_CLEAR,
    EQUITY_TARGET_NORMAL,
    LINE_CLEAR,
    LINE_FULL,
    MAX_POSITIONS,
    MAX_WEIGHT,
    SHORT_HOLD_DAYS,
    STOP_LOSS_PCT,
    TAKE_PROFIT_PCT,
    TOTAL_CASH,
)
from ai_sim.portfolio_ops import active_positions, buy_by_amount, cash_available, equity_ratio, sell_all
from ai_sim.universe import UniverseEntry, build_universe
from sim_portfolio import _norm_code


@dataclass
class Decision:
    action: str  # buy | sell | hold | rebalance
    name: str
    code: str
    reason: str
    style: str = "短线"
    amount: float = 0.0


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
        out[s["code"]] = s
    return out


def _target_equity_ratio(sh_close: float | None) -> tuple[float, str]:
    if sh_close is None:
        return EQUITY_TARGET_NORMAL, "指数缺失，按默认仓位"
    if sh_close < LINE_CLEAR:
        return EQUITY_TARGET_BELOW_CLEAR, f"上证 {sh_close:.2f} < {LINE_CLEAR}（4033 软约束降仓）"
    if sh_close >= LINE_FULL:
        return min(0.85, EQUITY_TARGET_NORMAL + 0.1), f"上证 {sh_close:.2f} ≥ {LINE_FULL}（可偏高仓位）"
    return EQUITY_TARGET_NORMAL, f"上证 {sh_close:.2f} 在 {LINE_CLEAR}–{LINE_FULL} 区间"


def plan_trades(tick_path: str) -> list[Decision]:
    universe = build_universe()
    quotes = _stock_map(tick_path)
    sh = _sh_index(tick_path)
    target_ratio, regime = _target_equity_ratio(sh)
    current_ratio = equity_ratio()
    pos = active_positions()
    held = {str(r["标的"]).strip(): _norm_code(r["代码"]) for _, r in pos.iterrows()}
    decisions: list[Decision] = []

    # 卖出：止损 / 止盈 / 超配降仓
    for _, row in pos.iterrows():
        name = str(row["标的"]).strip()
        code = _norm_code(row.get("代码"))
        cost = float(row["成本"] or 0)
        q = quotes.get(code, {})
        price = q.get("price") or float(row.get("现价") or cost)
        if cost <= 0:
            continue
        pnl_pct = (price - cost) / cost * 100
        if pnl_pct <= STOP_LOSS_PCT:
            decisions.append(Decision("sell", name, code, f"止损 {pnl_pct:.1f}%", "短线"))
        elif pnl_pct >= TAKE_PROFIT_PCT:
            decisions.append(Decision("sell", name, code, f"止盈 {pnl_pct:.1f}%", "短线"))
        elif current_ratio > target_ratio + 0.05:
            decisions.append(
                Decision("sell", name, code, f"降仓：{regime}（当前仓位 {current_ratio:.0%} > 目标 {target_ratio:.0%}）", "风控")
            )

    # 买入：强势池 + 未持仓 + 仓位不足
    if len(held) >= MAX_POSITIONS:
        return decisions
    if current_ratio >= target_ratio - 0.02:
        return decisions

    cash = cash_available()
    slot = min(MAX_WEIGHT * TOTAL_CASH, cash / max(1, MAX_POSITIONS - len(held)))

    candidates: list[tuple[float, UniverseEntry]] = []
    for e in universe:
        if e.name in held or e.code in held.values():
            continue
        if e.source not in ("track", "daily_gain"):
            continue
        q = quotes.get(e.code, {})
        price = q.get("price")
        if price is None:
            continue
        # 优先 daily_gain 来源
        score = 1.0 if e.source == "daily_gain" else 0.5
        if e.source == "track":
            score += 0.3
        candidates.append((score, e))

    candidates.sort(key=lambda x: -x[0])
    for _, e in candidates[: MAX_POSITIONS - len(held)]:
        if slot < 50_000:
            break
        style = "短线" if e.source == "daily_gain" else "波段"
        decisions.append(
            Decision(
                "buy",
                e.name,
                e.code,
                f"{regime}；来源 {e.source}；目标仓位 {target_ratio:.0%}",
                style,
                slot,
            )
        )
    return decisions


def execute_decisions(decisions: list[Decision]) -> list[dict]:
    results: list[dict] = []
    for d in decisions:
        if d.action == "sell":
            r = sell_all(d.name, reason=d.reason)
            if r:
                r["style"] = d.style
                r["reason"] = d.reason
                results.append(r)
        elif d.action == "buy" and d.amount > 0:
            r = buy_by_amount(d.name, d.code, d.amount, style=d.style)
            if r:
                r["reason"] = d.reason
                results.append(r)
    return results
