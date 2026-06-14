"""Graph 预算：读 llm_budget + 运行时降级。"""
from __future__ import annotations

from graph.state import BudgetLedger, GraphState


def load_graph_config() -> dict:
    from llm_budget import load_budget

    cfg = load_budget()
    g = cfg.get("graph") or {}
    if not isinstance(g, dict):
        g = {}
    return {
        "enabled": bool(g.get("enabled", False)),
        "max_debate_rounds": int(g.get("max_debate_rounds") or 1),
        "analyst_batch_mode": str(g.get("analyst_batch_mode") or "batch"),
        "skip_on_budget_pct": float(g.get("skip_on_budget_pct") or 80),
        "per_call_usd_est": float(g.get("per_call_usd_est") or 0.85),
        "cap_usd": float(cfg.get("per_sug_usd_cap") or 5.0),
    }


def init_budget(*, task: str = "sug") -> BudgetLedger:
    from llm_budget import load_budget

    cfg = load_budget()
    cap = float(cfg.get("per_sug_usd_cap") if task == "sug" else cfg.get("per_qry_usd_cap") or 2.0)
    return BudgetLedger(cap_usd=cap)


def record_llm_call(state: GraphState, *, usage_usd: float, tokens: int = 0) -> None:
    state.budget.spent_usd += usage_usd
    state.budget.llm_calls += 1
    state.budget.tokens_estimated += tokens


def maybe_degrade(state: GraphState, cfg: dict | None = None) -> None:
    cfg = cfg or load_graph_config()
    pct = state.budget.pct_used()
    threshold = float(cfg.get("skip_on_budget_pct") or 80)
    if pct >= threshold:
        state.budget.degraded = True
        state.budget.skip_debate = True
        if pct >= 95:
            state.budget.analyst_mode = "skip"
        elif pct >= threshold:
            state.budget.analyst_mode = "batch"


def budget_allows_call(state: GraphState, *, est_usd: float | None = None) -> bool:
    cfg = load_graph_config()
    est = est_usd if est_usd is not None else float(cfg.get("per_call_usd_est") or 0.85)
    return state.budget.remaining() >= est
