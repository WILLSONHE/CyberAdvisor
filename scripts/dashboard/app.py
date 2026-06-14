"""CyberAdvisor 本地看板（只读）。"""
from __future__ import annotations

import os
import sys

import streamlit as st

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from dashboard.data import holders  # noqa: E402
from llm_budget import estimate_sug_cost_usd, load_budget, save_budget  # noqa: E402

st.set_page_config(
    page_title="CyberAdvisor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("CyberAdvisor 看板")
st.caption("只读展示 · 数据由 daily.bat / Cursor / 飞书维护")

with st.sidebar:
    st.header("LLM 预算")
    cfg = load_budget()
    cap = st.number_input(
        "单次 sug 上限 (USD)",
        min_value=0.5,
        max_value=50.0,
        value=float(cfg.get("per_sug_usd_cap") or 5.0),
        step=0.5,
        key="sug_cap",
    )
    qry_cap = st.number_input(
        "单次 qry 上限 (USD)",
        min_value=0.5,
        max_value=20.0,
        value=float(cfg.get("per_qry_usd_cap") or 2.0),
        step=0.5,
        key="qry_cap",
    )
    mode = st.selectbox(
        "多 Agent 模式",
        options=["orchestrator_stub", "cursor_parallel", "langgraph_single", "hybrid"],
        index=0,
        help="cursor_parallel = 多个 Cursor Cloud Agent 并行扮演角色",
    )
    est = estimate_sug_cost_usd({**cfg, "per_sug_usd_cap": cap})
    st.metric("预估单次 sug", f"${est['estimated_usd']:.2f}", f"上限 ${cap:.2f}")
    if est["estimated_usd"] > cap:
        st.warning("预估超出上限，请减少角色数或降低 debate 轮数")
    if st.button("保存预算配置"):
        cfg["per_sug_usd_cap"] = cap
        cfg["per_qry_usd_cap"] = qry_cap
        cfg["multi_agent_mode"] = mode
        save_budget(cfg)
        st.success("已写入 Wiki/数据/llm_budget.json")

    st.divider()
    st.markdown("**持有人**")
    for h in holders():
        st.text(h)

st.markdown(
    """
左侧导航进入各页：

- **总览** — 持仓 + 缠论 + 七轨 + 可建仓
- **K 线** — 日 K / 5 分钟 + ZD/ZG/保护位
- **报告** — SugVault sug / 根目录分析 md
- **Outlook 复盘** — 预测登记与复盘 md
- **缠论回测** — 买点命中率报告
- **Graph 进度** — 多 Agent 12 阶段 / 预算 / graph_runs

术语：`Wiki/投资方法论/缠论-术语与读表指南.md`（看板总览/回测页内可展开）

> 维护数据仍用飞书 Bot + Cursor；本看板不写入 Wiki。Graph CLI：`graph.bat`
"""
)
