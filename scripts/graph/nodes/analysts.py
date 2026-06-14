"""Graph 节点：七分析师 + Quality Gate。"""
from __future__ import annotations

from graph.budget import budget_allows_call, maybe_degrade, record_llm_call
from graph.llm import resolve_llm
from graph.prompts import analyst_prompt
from graph.stages import ANALYST_ROLES
from graph.state import GraphState


def run_analysts(state: GraphState, *, force_live: bool = False) -> GraphState:
    maybe_degrade(state)
    if state.budget.analyst_mode == "skip":
        state.analyst_reports["skipped"] = "预算不足，跳过 LLM 分析师"
        return state

    llm = resolve_llm(dry_run=state.dry_run, force_live=force_live)
    state_dict = state.to_dict()

    if state.budget.analyst_mode == "batch" or state.budget.degraded:
        if not budget_allows_call(state):
            state.analyst_reports["skipped"] = "预算不足"
            return state
        roles_text = "\n".join(f"- {label}" for _, label in ANALYST_ROLES)
        prompt = (
            f"依次从以下视角各写一段简短分析（共 7 段，每段 3 bullet）：\n{roles_text}\n\n"
            + analyst_prompt("market", "Market Analyst", state_dict)
        )
        resp = llm.complete(role="analysts_batch", prompt=prompt)
        record_llm_call(state, usage_usd=float(resp.get("usage_usd") or 0), tokens=int(resp.get("tokens") or 0))
        state.analyst_reports["batch"] = resp.get("text") or ""
        return state

    for key, label in ANALYST_ROLES:
        if not budget_allows_call(state):
            state.errors.append(f"预算耗尽，跳过 {label}")
            break
        prompt = analyst_prompt(key, label, state_dict)
        resp = llm.complete(role=key, prompt=prompt)
        record_llm_call(state, usage_usd=float(resp.get("usage_usd") or 0), tokens=int(resp.get("tokens") or 0))
        state.analyst_reports[key] = resp.get("text") or ""
    return state


def run_quality_gate(state: GraphState) -> GraphState:
    gaps: list[str] = []
    passed: list[str] = []

    idx = state.index_chan
    if not idx.get("ok"):
        gaps.append("指数缠论不可用")
    elif idx.get("action") == "sell" or "一卖" in str(idx.get("buy_point") or ""):
        gaps.append("指数一卖/减仓 — 禁止新开仓")

    for code, v in state.stock_verdicts.items():
        if not v.get("ok"):
            gaps.append(f"{code}：七轨/verdict 失败")
            continue
        if not v.get("can_open") and v.get("open_block_reason"):
            gaps.append(f"{code}：{v.get('open_block_reason')}")
        else:
            passed.append(code)

    state.quality_gate = {
        "passed": passed,
        "gaps": gaps,
        "ok": len(gaps) == 0,
        "summary": f"通过 {len(passed)} 只；缺口 {len(gaps)} 项",
    }
    return state
