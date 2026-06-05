"""AI 模拟盘现金账本（买卖实际增减，非「500万减成本」估算）。"""
from __future__ import annotations

import json
import os

from ai_sim.config import ROOT, SIM_HOLDER, SIM_XLSX, TOTAL_CASH

LEDGER_PATH = os.path.join(ROOT, "Wiki", "数据", "AI模拟盘现金.json")


def _read_ledger() -> dict | None:
    if not os.path.isfile(LEDGER_PATH):
        return None
    try:
        return json.loads(open(LEDGER_PATH, encoding="utf-8").read())
    except Exception:
        return None


def _write_ledger(cash: float) -> None:
    os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
    payload = {"cash": round(float(cash), 2), "initial": TOTAL_CASH}
    with open(LEDGER_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def reconcile_from_xlsx() -> float:
    """从 xlsx 历史行重建现金（买入扣款、已卖出按卖出时现价回款）。"""
    if not os.path.isfile(SIM_XLSX):
        return TOTAL_CASH
    import pandas as pd

    from sim_portfolio import SOLD_COL, _is_data_row, _is_sold, _load_df, _norm_code

    df = _load_df()
    if df.empty:
        return TOTAL_CASH
    cash = float(TOTAL_CASH)
    for _, row in df.iterrows():
        if not _is_data_row(row):
            continue
        if str(row.get("持有人", "")).strip() != SIM_HOLDER:
            continue
        cost = float(row.get("成本") or 0)
        shares = int(float(row.get("股数") or 0))
        if cost <= 0 or shares <= 0:
            continue
        invest = cost * shares
        cash -= invest
        if _is_sold(row.get(SOLD_COL)):
            exit_px = float(row.get("现价") or cost)
            cash += exit_px * shares
    return max(0.0, cash)


def ensure_ledger(*, force_reconcile: bool = False) -> float:
    if force_reconcile or _read_ledger() is None:
        cash = reconcile_from_xlsx()
        _write_ledger(cash)
        return cash
    return float(_read_ledger()["cash"])


def get_cash() -> float:
    return ensure_ledger()


def on_buy(invest: float) -> float:
    cash = get_cash() - invest
    _write_ledger(cash)
    return cash


def on_sell(proceeds: float) -> float:
    cash = get_cash() + proceeds
    _write_ledger(cash)
    return cash
