"""Sug / 分析报告。"""
from __future__ import annotations

import glob
import os
import sys

import streamlit as st

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
ROOT = os.path.abspath(os.path.join(SCRIPTS, ".."))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from dashboard.data import list_sug_reports, read_text  # noqa: E402

st.header("报告")

tab1, tab2 = st.tabs(["SugVault", "根目录分析 md"])

with tab1:
    reports = list_sug_reports()
    if not reports:
        st.info("SugVault 暂无报告；在 Cursor 或飞书 agent sug 生成后刷新")
    else:
        labels = [
            f"{r['date']} {r['session'] or ''} · {r['holder']} · {r['name']}".strip()
            for r in reports
        ]
        pick = st.selectbox("选择 sug", labels, index=0)
        path = reports[labels.index(pick)]["path"]
        st.markdown(read_text(path))

with tab2:
    root_mds = sorted(glob.glob(os.path.join(ROOT, "*_分析.md")), reverse=True)
    root_mds += sorted(glob.glob(os.path.join(ROOT, "20*_*_分析.md")), reverse=True)
    seen = set()
    uniq = []
    for p in root_mds:
        if p in seen:
            continue
        seen.add(p)
        uniq.append(p)
    if not uniq:
        st.info("根目录无 *_分析.md")
    else:
        pick2 = st.selectbox("选择分析", [os.path.basename(p) for p in uniq[:50]], index=0)
        path2 = next(p for p in uniq if os.path.basename(p) == pick2)
        st.markdown(read_text(path2))
