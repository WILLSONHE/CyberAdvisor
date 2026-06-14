"""Graph 报告渲染。"""
from __future__ import annotations

from graph.prompts import final_sug_prompt
from graph.state import GraphState


def render_graph_appendix(state: GraphState) -> str:
    """Graph 结构化附录（可嵌入 sug 或单独存档）。"""
    lines = [
        f"<!-- graph analysis_id={state.analysis_id} dry_run={state.dry_run} -->",
        f"# Graph 管线附录 · {state.holder}",
        "",
        f"- **analysis_id**: `{state.analysis_id}`",
        f"- **预算**: ${state.budget.spent_usd:.2f} / ${state.budget.cap_usd:.2f} "
        f"（LLM 调用 {state.budget.llm_calls} 次，degraded={state.budget.degraded}）",
        "",
        "## Quality Gate",
        state.quality_gate.get("summary", "—"),
        "",
    ]
    for g in state.quality_gate.get("gaps") or []:
        lines.append(f"- ⚠ {g}")
    lines.extend(["", "## Portfolio Manager", state.portfolio_manager or "（无）", ""])
    if state.hard_gate:
        lines.extend(["## Hard Gate", "```json", _json(state.hard_gate), "```", ""])
    return "\n".join(lines)


def _json(obj) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, indent=2)[:8000]


def render_final_sug(state: GraphState, *, force_live: bool = False) -> GraphState:
    """最终 sug：Graph 上下文 + 单次 PM/Reporter LLM（或 dry-run stub）。"""
    from graph.budget import budget_allows_call, record_llm_call
    from graph.llm import resolve_llm

    sd = state.to_dict()
    sd["budget"] = {
        "spent_usd": state.budget.spent_usd,
        "cap_usd": state.budget.cap_usd,
    }
    prompt = final_sug_prompt(state.holder, sd, session=state.session)

    if state.dry_run or not budget_allows_call(state, est_usd=1.2):
        state.final_markdown = render_graph_appendix(state) + "\n\n---\n\n" + (
            "（dry-run / 预算不足：未调用最终 sug Reporter；"
            "启用 `GRAPH_PIPELINE_ENABLED=1` 后由 Cloud Agent 生成完整 trade_template。）\n"
        )
        return state

    llm = resolve_llm(dry_run=False, force_live=force_live)
    resp = llm.complete(role="final_sug_reporter", prompt=prompt, max_chars=28000)
    record_llm_call(state, usage_usd=float(resp.get("usage_usd") or 0), tokens=int(resp.get("tokens") or 0))
    body = (resp.get("text") or "").strip()
    meta = (
        f"<!-- graph analysis_id={state.analysis_id} "
        f"spent_usd={state.budget.spent_usd:.2f} -->"
    )
    state.final_markdown = meta + "\n\n" + body
    return state
