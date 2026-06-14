"""缠论回测报告。"""
from __future__ import annotations

import os
import subprocess
import sys

import pandas as pd
import streamlit as st

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
ROOT = os.path.abspath(os.path.join(SCRIPTS, ".."))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from dashboard.data import latest_backtest, read_text, render_chan_glossary_expander  # noqa: E402

st.header("缠论回测")

render_chan_glossary_expander()

lookback = st.slider("回看日历日", 60, 365, 120, step=30)
hit_pct = st.slider("命中阈值 %", 1.0, 10.0, 3.0, step=0.5)

if st.button("运行回测（portfolio 全持仓）", type="primary"):
    with st.spinner("walk-forward 中…"):
        p = subprocess.run(
            [
                sys.executable,
                os.path.join(SCRIPTS, "chan", "backtest.py"),
                "--universe",
                "portfolio",
                "--lookback",
                str(lookback),
                "--hit-pct",
                str(hit_pct),
                "--write",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
    if p.returncode == 0:
        st.success(p.stdout or "完成")
        st.cache_data.clear()
    else:
        st.error((p.stderr or p.stdout or "失败")[-2000:])

report = latest_backtest()
if not report:
    st.info("尚无回测报告；点击上方按钮或运行 scripts/chan/backtest.py --write")
    st.stop()

st.caption(f"报告：`{report.get('_path', '')}` · 信号数 {report.get('signal_count', 0)}")

bp = report.get("by_buy_point") or {}
if bp:
    rows = []
    for k, v in bp.items():
        if not v.get("n"):
            continue
        rows.append({"买点": k, **v})
    if rows:
        st.subheader("按买点类型")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

hz = report.get("by_horizon") or {}
if hz:
    rows2 = [{"周期": f"{k}日", **v} for k, v in hz.items() if v.get("n")]
    if rows2:
        st.subheader("按持有周期")
        st.dataframe(pd.DataFrame(rows2), use_container_width=True, hide_index=True)

oos = report.get("oos") or {}
if oos.get("out_of_sample_horizons"):
    st.subheader("样本外 (OOS)")
    st.json(oos.get("out_of_sample_horizons"))

md_path = report.get("_md")
if md_path and os.path.isfile(md_path):
    with st.expander("Markdown 报告"):
        st.markdown(read_text(md_path))
