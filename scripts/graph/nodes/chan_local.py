"""Graph 节点：本地缠论 + 七轨。"""
from __future__ import annotations

from graph.state import GraphState


def run_chan_local(state: GraphState) -> GraphState:
    from chan.analyze import analyze_code, analyze_index
    from bollinger_utils import build_stock_verdict
    from portfolio_utils import holdings_for_holder, pad_a_share_code

    state.index_chan = analyze_index()
    rows = holdings_for_holder(state.holder) if state.holder else []
    state.holdings = rows

    for h in rows:
        code = pad_a_share_code(h.get("code", ""))
        name = str(h.get("name") or code)
        if not code or len(code) != 6:
            continue
        state.stock_chans[code] = analyze_code(code, name=name, has_position=True)
        state.stock_verdicts[code] = build_stock_verdict(
            code,
            name=name,
            has_position=True,
            index_chan=state.index_chan,
        )
    return state
