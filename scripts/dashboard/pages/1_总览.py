"""持仓总览。"""
from __future__ import annotations

import sys
import os

import pandas as pd
import streamlit as st

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from dashboard.data import all_holdings, chan_snapshot, render_chan_glossary_expander, stock_verdict  # noqa: E402

st.header("持仓总览")

render_chan_glossary_expander()

refresh = st.button("刷新缠论/七轨", type="primary")
cache_ttl = 0 if refresh else 300


@st.cache_data(ttl=cache_ttl, show_spinner="加载研判…")
def _row(code: str, name: str, has_position: bool) -> dict:
    chan = chan_snapshot(code, name, has_position=has_position)
    verdict = stock_verdict(code, name, has_position=has_position)
    return {
        "chan_ok": chan.get("ok"),
        "买点": chan.get("buy_point", "—"),
        "趋势": chan.get("trend_day", "—"),
        "保护位": chan.get("protect_price"),
        "ZD": chan.get("ZD"),
        "ZG": chan.get("ZG"),
        "score": chan.get("score"),
        "七轨": (verdict.get("boll") or {}).get("zone") if verdict.get("ok") else "—",
        "可建仓": verdict.get("can_open") if verdict.get("ok") else None,
        "门禁": verdict.get("open_block_reason") or "",
    }


rows = []
for h in all_holdings():
    code = h["code"]
    meta = _row(code, h["name"], has_position=True)
    rows.append(
        {
            "持有人": h["holder"],
            "标的": h["name"],
            "代码": code,
            "现价": h.get("price"),
            "成本": h.get("cost"),
            **{k: v for k, v in meta.items() if k != "chan_ok"},
        }
    )

if not rows:
    st.info("portfolio.py 无持仓；请先 sync 持仓.xlsx")
else:
    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "可建仓": st.column_config.CheckboxColumn("可建仓"),
            "保护位": st.column_config.NumberColumn(format="%.2f"),
            "ZD": st.column_config.NumberColumn(format="%.2f"),
            "ZG": st.column_config.NumberColumn(format="%.2f"),
        },
    )

    sel = st.selectbox("查看单标的缠论详情", options=[f"{r['标的']} ({r['代码']})" for r in rows])
    if sel:
        idx = [f"{r['标的']} ({r['代码']})" for r in rows].index(sel)
        code = rows[idx]["代码"]
        name = rows[idx]["标的"]
        chan = chan_snapshot(code, name, has_position=True)
        if chan.get("ok"):
            st.subheader(f"{name} · 缠论")
            c1, c2, c3 = st.columns(3)
            c1.metric("买点", chan.get("buy_point"))
            c2.metric("保护位", f"{chan.get('protect_price'):.2f}")
            c3.metric("score", f"{chan.get('score'):.2f}")
            st.info(chan.get("guidance") or chan.get("buy_reason", ""))
            st.caption(chan.get("buy_reason", ""))
        else:
            st.error(chan.get("error", "分析失败"))
