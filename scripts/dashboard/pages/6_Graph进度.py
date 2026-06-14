"""Graph 多 Agent 编排进度。"""
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

from dashboard.data import (  # noqa: E402
    graph_pipeline_enabled,
    graph_run_markdown,
    holders,
    list_graph_progress,
    load_graph_progress,
)
from llm_budget import load_budget  # noqa: E402

st.header("Graph 进度")

enabled = graph_pipeline_enabled()
cfg = load_budget()
graph_cfg = cfg.get("graph") or {}

if enabled:
    st.success("GRAPH_PIPELINE_ENABLED=1 · 可 `graph.bat sug Wilson --live`")
else:
    st.info(
        "Graph 默认关闭（GRAPH_PIPELINE_ENABLED=0）。"
        "可 dry-run 试跑；启用后飞书 `agent graph sug` / `graph.bat … --live`。"
    )

c1, c2, c3, c4 = st.columns(4)
c1.metric("单次 sug 上限", f"${cfg.get('per_sug_usd_cap', 5):.1f}")
c2.metric("辩论轮数", graph_cfg.get("max_debate_rounds", 1))
c3.metric("预算降级线", f"{graph_cfg.get('skip_on_budget_pct', 80)}%")
c4.metric("分析师模式", graph_cfg.get("analyst_batch_mode", "batch"))

st.divider()
st.subheader("试跑 Graph（dry-run）")

h_col, s_col, btn_col = st.columns([2, 1, 1])
with h_col:
    holder_pick = st.selectbox("持有人", holders() or ["Wilson"], key="graph_holder")
with s_col:
    session_pick = st.selectbox("盘次", ["", "早盘", "午盘"], format_func=lambda x: x or "未指定")
with btn_col:
    st.write("")
    run_dry = st.button("dry-run sug", type="primary", use_container_width=True)

if run_dry:
    args = [sys.executable, os.path.join(SCRIPTS, "graph", "runner.py"), "sug", holder_pick]
    if session_pick:
        args.append(session_pick)
    args.append("--dry-run")
    with st.spinner("Graph 管线运行中…"):
        p = subprocess.run(
            args,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
    if p.returncode == 0:
        st.success(p.stdout or "完成")
        st.cache_data.clear()
    else:
        st.error((p.stderr or p.stdout or "失败")[-2500:])

records = list_graph_progress(40)
if not records:
    st.warning("尚无进度 JSON。运行 `graph.bat sug Wilson --dry-run` 或上方按钮。")
    st.stop()

st.subheader("最近运行")

rows = []
for r in records:
    b = r.get("budget") or {}
    rows.append(
        {
            "analysis_id": r.get("analysis_id"),
            "任务": r.get("task"),
            "持有人": r.get("holder"),
            "盘次": r.get("session") or "—",
            "阶段": r.get("current_label") or r.get("current_stage"),
            "预算%": b.get("pct"),
            "spent": b.get("spent_usd"),
            "calls": b.get("llm_calls"),
            "dry_run": r.get("dry_run"),
            "updated": r.get("updated_at"),
        }
    )
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

ids = [r.get("analysis_id") for r in records if r.get("analysis_id")]
pick = st.selectbox("查看详情", ids, index=0)
detail = load_graph_progress(pick) if pick else None

if not detail:
    st.stop()

st.subheader(f"详情 · `{pick}`")

b = detail.get("budget") or {}
m1, m2, m3, m4 = st.columns(4)
m1.metric("已用预算", f"${b.get('spent_usd', 0):.2f}", f"上限 ${b.get('cap_usd', 5):.2f}")
m2.metric("使用率", f"{b.get('pct', 0)}%")
m3.metric("LLM 调用", b.get("llm_calls", 0))
m4.metric("降级", "是" if b.get("degraded") else "否")

stages = detail.get("stages") or []
done_n = sum(1 for s in stages if s.get("done"))
if stages:
    st.progress(min(1.0, done_n / len(stages)), text=f"{done_n}/{len(stages)} 阶段")

for s in stages:
    mark = "✅" if s.get("done") else ("▶️" if s.get("current") else "⬜")
    st.markdown(f"{mark} **{s.get('label', s.get('id'))}** `{s.get('id')}`")

if detail.get("errors"):
    st.error("最近错误")
    for e in detail["errors"]:
        st.code(e)

md = graph_run_markdown(pick) if pick else None
if md:
    with st.expander("graph_runs 输出 Markdown", expanded=False):
        st.markdown(md)
else:
    st.caption(f"未找到 Wiki/数据/graph_runs/{pick}.md")

st.caption("CLI：`graph.bat status` · `graph.bat sug Wilson --dry-run` · `graph.bat sug Wilson 午盘 --live`")
