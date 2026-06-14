"""Outlook 预测复盘。"""
from __future__ import annotations

import json
import os
import sys

import streamlit as st

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from dashboard._paths import LOG_PATH, PARAMS_PATH  # noqa: E402
from dashboard.data import list_outlook_reviews, outlook_summary, read_text  # noqa: E402

st.header("Outlook 复盘")

summary = outlook_summary()
c1, c2, c3 = st.columns(3)
c1.metric("登记记录", summary.get("records", 0))
c2.metric("已复盘 horizon", summary.get("reviewed", 0))
c3.metric("待复盘", summary.get("pending", 0))

if os.path.isfile(PARAMS_PATH):
    with open(PARAMS_PATH, encoding="utf-8") as f:
        params = json.load(f)
    st.caption(f"参数版本：`{params.get('version') or params.get('params_version', '—')}`")

reviews = list_outlook_reviews()
if reviews:
    pick = st.selectbox("复盘 md", [os.path.basename(p) for p in reviews[:40]], index=0)
    path = next(p for p in reviews if os.path.basename(p) == pick)
    with st.expander("全文", expanded=True):
        st.markdown(read_text(path))
else:
    st.info("运行 `python scripts/outlook_tracker.py batch` 生成复盘 md")

st.divider()
st.subheader("最近登记（抽样）")
if os.path.isfile(LOG_PATH):
    try:
        data = json.loads(open(LOG_PATH, encoding="utf-8").read())
        recs = (data.get("records") or [])[-15:]
        for rec in reversed(recs):
            code = rec.get("code")
            name = rec.get("name")
            d = rec.get("date")
            st.markdown(f"**{d}** · {name} ({code}) · source={rec.get('source')}")
            hz = rec.get("horizons") or {}
            cols = st.columns(len(hz) or 1)
            for i, (k, h) in enumerate(sorted(hz.items())):
                if not isinstance(h, dict):
                    continue
                with cols[i % len(cols)]:
                    st.caption(k)
                    st.text(f"{h.get('lo')} – {h.get('hi')}")
                    if h.get("review"):
                        st.success("已复盘")
    except (OSError, json.JSONDecodeError) as exc:
        st.error(str(exc))
