"""Graph 节点：多空辩论 + RM + Trader + 风控 + PM。"""
from __future__ import annotations

from graph.budget import budget_allows_call, load_graph_config, record_llm_call
from graph.llm import resolve_llm
from graph.prompts import (
    debate_prompt,
    portfolio_manager_prompt,
    research_manager_prompt,
    risk_tier_prompt,
    trader_prompt,
)
from graph.stages import RISK_TIERS
from graph.state import GraphState


def _llm_step(state: GraphState, *, role: str, prompt: str, force_live: bool = False) -> str:
    if not budget_allows_call(state):
        state.errors.append(f"预算不足，跳过 {role}")
        return ""
    llm = resolve_llm(dry_run=state.dry_run, force_live=force_live)
    resp = llm.complete(role=role, prompt=prompt)
    record_llm_call(state, usage_usd=float(resp.get("usage_usd") or 0), tokens=int(resp.get("tokens") or 0))
    return str(resp.get("text") or "")


def run_debate(state: GraphState, *, force_live: bool = False) -> GraphState:
    if state.budget.skip_debate:
        state.bull_case = "（预算降级：跳过辩论）"
        state.bear_case = "（预算降级：跳过辩论）"
        return state

    cfg = load_graph_config()
    rounds = max(0, int(cfg.get("max_debate_rounds") or 1))
    sd = state.to_dict()
    opponent_bear = ""
    opponent_bull = ""
    for r in range(rounds):
        if not budget_allows_call(state):
            break
        state.bull_case = _llm_step(
            state,
            role=f"bull_r{r}",
            prompt=debate_prompt("Bull", sd, opponent=opponent_bear),
            force_live=force_live,
        )
        state.bear_case = _llm_step(
            state,
            role=f"bear_r{r}",
            prompt=debate_prompt("Bear", sd, opponent=state.bull_case),
            force_live=force_live,
        )
        state.debate_rounds.append({"round": r + 1, "bull": state.bull_case[:500], "bear": state.bear_case[:500]})
        opponent_bull = state.bull_case
        opponent_bear = state.bear_case
    return state


def run_research_manager(state: GraphState, *, force_live: bool = False) -> GraphState:
    state.research_manager = _llm_step(
        state,
        role="research_manager",
        prompt=research_manager_prompt(state.to_dict()),
        force_live=force_live,
    )
    return state


def run_trader(state: GraphState, *, force_live: bool = False) -> GraphState:
    state.trader_proposal = _llm_step(
        state,
        role="trader",
        prompt=trader_prompt(state.to_dict()),
        force_live=force_live,
    )
    return state


def run_risk_tiers(state: GraphState, *, force_live: bool = False) -> GraphState:
    sd = state.to_dict()
    for tier in RISK_TIERS:
        if not budget_allows_call(state):
            state.risk_tiers[tier] = "（预算不足，跳过）"
            continue
        state.risk_tiers[tier] = _llm_step(
            state,
            role=f"risk_{tier}",
            prompt=risk_tier_prompt(tier, sd),
            force_live=force_live,
        )
    return state


def run_portfolio_manager(state: GraphState, *, force_live: bool = False) -> GraphState:
    state.portfolio_manager = _llm_step(
        state,
        role="portfolio_manager",
        prompt=portfolio_manager_prompt(state.to_dict()),
        force_live=force_live,
    )
    return state
