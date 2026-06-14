"""12 阶段进度定义（对齐 astock 展示）。"""
from __future__ import annotations

PIPELINE_STAGES: tuple[tuple[str, str], ...] = (
    ("init", "初始化"),
    ("chan_local", "缠论本地分析"),
    ("quality_gate", "Quality Gate"),
    ("analysts", "七分析师"),
    ("debate", "多空辩论"),
    ("research_manager", "研究经理"),
    ("hard_gate", "缠论硬门禁"),
    ("trader", "交易员提案"),
    ("risk_tiers", "三档风控"),
    ("portfolio_manager", "投资组合经理"),
    ("render", "报告渲染"),
    ("done", "完成"),
)

STAGE_IDS = [s[0] for s in PIPELINE_STAGES]
STAGE_LABELS = {s[0]: s[1] for s in PIPELINE_STAGES}

ANALYST_ROLES: tuple[tuple[str, str], ...] = (
    ("market", "Market Analyst"),
    ("fundamentals", "Fundamentals Analyst"),
    ("news", "News Analyst"),
    ("policy", "Policy Analyst"),
    ("hot_money", "Hot Money Analyst"),
    ("lockup", "Lockup Analyst"),
    ("sentiment", "Sentiment Analyst"),
)

RISK_TIERS = ("aggressive", "neutral", "conservative")
