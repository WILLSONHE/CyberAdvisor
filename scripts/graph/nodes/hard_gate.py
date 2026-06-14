"""Graph 节点：缠论硬门禁汇总。"""
from __future__ import annotations

from graph.state import GraphState


def run_hard_gate(state: GraphState) -> GraphState:
    from chan.policy import allows_new_buy, compact_chan

    idx_c = compact_chan(state.index_chan)
    per_stock: dict[str, dict] = {}
    for code, ch in state.stock_chans.items():
        stock_c = compact_chan(ch)
        ok, reason = allows_new_buy(stock_c, idx_c)
        v = state.stock_verdicts.get(code) or {}
        per_stock[code] = {
            "name": ch.get("name") or code,
            "buy_point": ch.get("buy_point"),
            "protect_price": ch.get("protect_price"),
            "allows_new_buy": ok,
            "reason": reason,
            "can_open_verdict": v.get("can_open"),
            "open_block_reason": v.get("open_block_reason"),
        }

    index_blocks = idx_c.get("ok") and (
        idx_c.get("action") == "sell" or "一卖" in str(idx_c.get("buy_point") or "")
    )
    state.hard_gate = {
        "index": idx_c,
        "index_blocks_new_buy": bool(index_blocks),
        "stocks": per_stock,
        "note": "缠论 hard_gate 优先于 PM/LLM 结论",
    }
    return state
