"""K 线图表。"""
from __future__ import annotations

import os
import sys

import plotly.graph_objects as go
import streamlit as st

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from dashboard.data import chan_snapshot, load_kline_df, unique_codes  # noqa: E402

st.header("K 线")

codes = unique_codes()
if not codes:
    st.warning("无标的")
    st.stop()

labels = [f"{name} ({code})" for code, name in codes]
choice = st.selectbox("标的", labels, index=0)
code = codes[labels.index(choice)][0]
name = codes[labels.index(choice)][1]
period = st.radio("周期", ["day", "5m"], horizontal=True, format_func=lambda x: "日 K" if x == "day" else "5 分钟")

limit = 240 if period == "day" else 400
df = load_kline_df(code, period, limit=limit)
if df is None or df.empty:
    st.error("K 线加载失败（检查 vipdoc / mootdx）")
    st.stop()

chan = chan_snapshot(code, name, has_position=False) if period == "day" else {"ok": False}

fig = go.Figure(
    data=[
        go.Candlestick(
            x=df["time"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name=code,
        )
    ]
)
if chan.get("ok"):
    zd, zg = chan.get("ZD"), chan.get("ZG")
    prot = chan.get("protect_price")
    for y, label, color in (
        (zd, "ZD", "green"),
        (zg, "ZG", "orange"),
        (prot, "保护位", "red"),
    ):
        if y:
            fig.add_hline(y=float(y), line_dash="dash", line_color=color, annotation_text=label)

fig.update_layout(
    title=f"{name} ({code}) · {period}",
    xaxis_rangeslider_visible=False,
    height=560,
    margin=dict(l=40, r=40, t=60, b=40),
)
st.plotly_chart(fig, use_container_width=True)

if chan.get("ok"):
    st.markdown(
        f"**缠论** {chan.get('buy_point')} · {chan.get('trend_day')} · "
        f"保护 {chan.get('protect_price'):.2f}"
    )
    if chan.get("guidance"):
        st.info(chan.get("guidance"))
    st.caption(chan.get("buy_reason", ""))
