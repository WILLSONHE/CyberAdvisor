"""AI 模拟盘持仓读写与成交。"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime

import pandas as pd

SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from ai_sim.cash import ensure_ledger, get_cash, on_buy, on_sell
from ai_sim.config import PRICE_SANITY_BAND, SIM_HOLDER, SIM_XLSX, TOTAL_CASH
from ai_sim.runtime_params import get as param
from portfolio_utils import fetch_spot_price
from sim_portfolio import (
    SOLD_COL,
    _calc_metrics,
    _calc_shares,
    _is_sold,
    _load_df,
    _norm_code,
    _portfolio_totals,
    _save_df,
    init_sim_xlsx,
)


def ensure_xlsx() -> None:
    if not os.path.isfile(SIM_XLSX):
        init_sim_xlsx()
    ensure_ledger()


def active_positions() -> pd.DataFrame:
    ensure_xlsx()
    df = _load_df()
    if df.empty:
        return df
    mask = (~df.apply(lambda r: _is_sold(r.get(SOLD_COL)), axis=1)) & (
        df["持有人"].astype(str).str.strip() == SIM_HOLDER
    )
    return df[mask].reset_index(drop=True)


def cash_available() -> float:
    return get_cash()


def total_assets() -> float:
    pos = active_positions()
    mkt = _portfolio_totals(pos)["total_mkt"] if not pos.empty else 0.0
    return get_cash() + mkt


def equity_ratio() -> float:
    """股票市值占总资金比例（与仓位目标同一口径）。"""
    pos = active_positions()
    mkt = _portfolio_totals(pos)["total_mkt"] if not pos.empty else 0.0
    return mkt / TOTAL_CASH if TOTAL_CASH else 0.0


def _price_suspect(price: float, cost: float) -> bool:
    if cost <= 0 or price <= 0:
        return True
    band = PRICE_SANITY_BAND
    ratio = price / cost
    return ratio < (1 - band) or ratio > (1 + band)


def _resolve_sell_price(
    code: str,
    cost: float,
    *,
    row_price: float,
    tick_quotes: dict[str, dict] | None = None,
) -> tuple[float, str]:
    """优先 tick 快照 → 行内现价 → 行情；异常偏离成本时拒绝错价。"""
    code = _norm_code(code)
    candidates: list[tuple[str, float]] = []
    if tick_quotes and code in tick_quotes:
        px = tick_quotes[code].get("price")
        if px and float(px) > 0:
            candidates.append(("tick", float(px)))
    if row_price > 0:
        candidates.append(("持仓现价", row_price))
    live = fetch_spot_price(code)
    if live and live > 0:
        candidates.append(("行情", live))
    if cost > 0:
        candidates.append(("成本", cost))

    for src, px in candidates:
        if not _price_suspect(px, cost):
            return px, src
    return cost if cost > 0 else (candidates[0][1] if candidates else 0.0), "成本(错价保护)"


def buy_by_amount(name: str, code: str, amount_yuan: float, *, style: str = "短线") -> dict | None:
    """按金额买入；返回成交摘要 dict。"""
    code = _norm_code(code)
    if not code:
        return None
    if amount_yuan < param("MIN_TRADE_YUAN"):
        return None
    if cash_available() < amount_yuan:
        amount_yuan = cash_available()
    if amount_yuan < param("MIN_TRADE_YUAN"):
        return None

    price = fetch_spot_price(code)
    if price is None or price <= 0:
        return None
    shares = _calc_shares(price, amount_yuan)
    cost = round(price, 4)
    invest = cost * shares
    if invest < param("MIN_TRADE_YUAN"):
        return None

    today = date.today()
    metrics = _calc_metrics(cost, shares, price, today, as_of=today)
    row = {
        "标的": name,
        "代码": code,
        "成本": cost,
        "股数": shares,
        "持有人": SIM_HOLDER,
        SOLD_COL: "N",
        "建仓日期": today.strftime("%Y-%m-%d"),
        **metrics,
    }
    df = _load_df()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    _save_df(df)
    on_buy(invest)
    return {
        "action": "buy",
        "name": name,
        "code": code,
        "shares": shares,
        "price": cost,
        "amount": invest,
        "style": style,
    }


def sell_all(
    name: str,
    *,
    reason: str = "",
    tick_quotes: dict[str, dict] | None = None,
) -> dict | None:
    df = _load_df()
    if df.empty:
        return None
    today = date.today()
    for idx, row in df.iterrows():
        if str(row.get("标的", "")).strip() != name.strip():
            continue
        if _is_sold(row.get(SOLD_COL)):
            continue
        if str(row.get("持有人", "")).strip() != SIM_HOLDER:
            continue
        code = _norm_code(row.get("代码"))
        cost = float(row.get("成本") or 0)
        shares = int(float(row.get("股数") or 0))
        row_px = float(row.get("现价") or row.get("成本") or 0)
        price, price_src = _resolve_sell_price(
            code, cost, row_price=row_px, tick_quotes=tick_quotes
        )
        open_d = datetime.strptime(str(row.get("建仓日期", today))[:10], "%Y-%m-%d").date()
        metrics = _calc_metrics(cost, shares, price, open_d, as_of=today)
        for k, v in metrics.items():
            df.at[idx, k] = v
        df.at[idx, SOLD_COL] = "Y"
        _save_df(df)
        proceeds = price * shares
        on_sell(proceeds)
        return {
            "action": "sell",
            "name": name,
            "code": code,
            "shares": shares,
            "price": price,
            "pnl": metrics["盈亏"],
            "pnl_pct": metrics["盈亏比"],
            "reason": reason,
            "price_src": price_src,
        }
    return None


def sync_prices() -> str:
    from sim_portfolio import sync_sim_prices

    return sync_sim_prices()
