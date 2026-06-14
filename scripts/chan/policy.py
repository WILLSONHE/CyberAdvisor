"""缠论决策门禁（全项目统一）。"""
from __future__ import annotations

from typing import Any

# 买点关键词（buy_point 字段）
_BUY_HINTS = ("一买", "二买", "三买")
_SELL_HINTS = ("一卖", "减仓", "观望/空")


def compact_chan(summary: dict[str, Any] | None) -> dict[str, Any]:
    if not summary or not summary.get("ok"):
        return {"ok": False, "error": summary.get("error") if summary else "无数据"}
    return {
        "ok": True,
        "structure": summary.get("structure"),
        "buy_point": summary.get("buy_point"),
        "action": summary.get("action"),
        "score": summary.get("score"),
        "protect_price": summary.get("protect_price"),
        "ZD": summary.get("ZD"),
        "ZG": summary.get("ZG"),
        "buy_reason": summary.get("buy_reason"),
    }


def is_buy_point(buy_point: str) -> bool:
    return any(h in (buy_point or "") for h in _BUY_HINTS)


def allows_new_buy(stock: dict[str, Any], index: dict[str, Any] | None = None) -> tuple[bool, str]:
    """模拟盘/报告：是否允许新开仓（缠论第一门禁）。"""
    if not stock.get("ok"):
        return False, stock.get("error") or "标的缠论不可用"
    bp = str(stock.get("buy_point") or "")
    score = float(stock.get("score") or 0)
    if index and index.get("ok"):
        ibp = str(index.get("buy_point") or "")
        if index.get("action") == "sell" or any(h in ibp for h in _SELL_HINTS if h != "观望/空"):
            if "一卖" in ibp or index.get("action") == "sell":
                return False, f"指数缠论：{ibp}"
        if index.get("action") == "wait" and score < 1.0 and not is_buy_point(bp):
            return False, f"指数缠论偏空（{ibp}），标的无强买点"
    if not is_buy_point(bp) and score <= 0:
        return False, f"无缠论买点（{bp or '—'}）"
    return True, bp or stock.get("buy_reason") or "缠论买点"


def should_force_sell(chan: dict[str, Any] | None, *, price: float | None) -> tuple[bool, str]:
    if not chan or not chan.get("ok"):
        return False, ""
    bp = str(chan.get("buy_point") or "")
    if chan.get("action") == "sell" or "一卖" in bp or "减仓" in bp:
        return True, bp or "缠论减仓"
    prot = chan.get("protect_price")
    if price and prot:
        try:
            if float(price) < float(prot) * 0.998:
                return True, f"破缠论保护位 {prot}"
        except (TypeError, ValueError):
            pass
    return False, ""


def score_for_ranking(chan: dict[str, Any] | None) -> float:
    if not chan or not chan.get("ok"):
        return -999.0
    return float(chan.get("score") or 0)
