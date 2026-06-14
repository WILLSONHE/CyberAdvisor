"""Graph 管线编排器（自研状态机，非 LangGraph）。"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from graph.analysis_id import new_analysis_id
from graph.budget import init_budget, load_graph_config, maybe_degrade
from graph.nodes.analysts import run_analysts, run_quality_gate
from graph.nodes.chan_local import run_chan_local
from graph.nodes.debate_pm import (
    run_debate,
    run_portfolio_manager,
    run_research_manager,
    run_risk_tiers,
    run_trader,
)
from graph.nodes.hard_gate import run_hard_gate
from graph.progress import write_progress
from graph.render import render_final_sug, render_graph_appendix
from graph.stages import STAGE_IDS
from graph.state import GraphState


def init_sug_state(holder: str, *, session: str | None = None, dry_run: bool = True) -> GraphState:
    return GraphState(
        analysis_id=new_analysis_id(holder=holder, task="sug"),
        task="sug",
        holder=holder,
        session=session,
        started_at=datetime.now().isoformat(timespec="seconds"),
        budget=init_budget(task="sug"),
        dry_run=dry_run,
        meta={"graph_version": "2026-06-15-orchestrator-v1"},
    )


def init_qry_state(question: str, *, dry_run: bool = True) -> GraphState:
    return GraphState(
        analysis_id=new_analysis_id(holder="qry", task="qry"),
        task="qry",
        question=question,
        started_at=datetime.now().isoformat(timespec="seconds"),
        budget=init_budget(task="qry"),
        dry_run=dry_run,
    )


def _mark_stage(state: GraphState, stage: str) -> None:
    state.current_stage = stage
    if stage not in state.stages_done:
        state.stages_done.append(stage)
    write_progress(state)


def run_sug_pipeline(
    holder: str,
    *,
    session: str | None = None,
    dry_run: bool | None = None,
    force_live: bool = False,
    on_stage: Callable[[GraphState, str], None] | None = None,
) -> GraphState:
    """完整 sug Graph 管线。默认 dry_run=True（不实际调用 Cursor）。"""
    cfg = load_graph_config()
    if dry_run is None:
        dry_run = not (cfg.get("enabled") or force_live)

    state = init_sug_state(holder, session=session, dry_run=bool(dry_run))
    _mark_stage(state, "init")

    steps: list[tuple[str, Callable[..., GraphState]]] = [
        ("chan_local", lambda s: run_chan_local(s)),
        ("quality_gate", lambda s: run_quality_gate(s)),
        ("analysts", lambda s: run_analysts(s, force_live=force_live)),
        ("debate", lambda s: run_debate(s, force_live=force_live)),
        ("research_manager", lambda s: run_research_manager(s, force_live=force_live)),
        ("hard_gate", lambda s: run_hard_gate(s)),
        ("trader", lambda s: run_trader(s, force_live=force_live)),
        ("risk_tiers", lambda s: run_risk_tiers(s, force_live=force_live)),
        ("portfolio_manager", lambda s: run_portfolio_manager(s, force_live=force_live)),
        ("render", lambda s: render_final_sug(s, force_live=force_live)),
    ]

    for stage_id, fn in steps:
        maybe_degrade(state)
        _mark_stage(state, stage_id)
        if on_stage:
            on_stage(state, stage_id)
        try:
            state = fn(state)
        except Exception as exc:
            state.errors.append(f"{stage_id}: {exc}")
            if stage_id == "render":
                state.final_markdown = render_graph_appendix(state)

    state.finished_at = datetime.now().isoformat(timespec="seconds")
    _mark_stage(state, "done")
    return state


def run_qry_pipeline(
    question: str,
    *,
    dry_run: bool | None = None,
    force_live: bool = False,
) -> GraphState:
    """深度 qry：简化链（缠论 + 分析师 batch + PM）。"""
    state = init_qry_state(question, dry_run=dry_run if dry_run is not None else True)
    state.holder = "qry"
    _mark_stage(state, "init")

    from chan.analyze import analyze_index
    from feishu.agent_prompts import guess_stock_in_text

    code, name = guess_stock_in_text(question)
    state.index_chan = analyze_index()
    if code:
        from chan.analyze import analyze_code

        state.stock_chans[code] = analyze_code(code, name=name or code, has_position=False)

    _mark_stage(state, "chan_local")
    run_quality_gate(state)
    _mark_stage(state, "quality_gate")
    run_analysts(state, force_live=force_live)
    _mark_stage(state, "analysts")
    run_hard_gate(state)
    _mark_stage(state, "hard_gate")
    run_portfolio_manager(state, force_live=force_live)
    _mark_stage(state, "portfolio_manager")

    from graph.prompts import _wiki_context

    state.final_markdown = (
        f"# qry Graph · `{state.analysis_id}`\n\n"
        f"**问题**：{question}\n\n"
        f"## PM\n{state.portfolio_manager}\n\n"
        f"## Wiki\n{_wiki_context(max_chars=6000)[:6000]}\n"
    )
    state.finished_at = datetime.now().isoformat(timespec="seconds")
    _mark_stage(state, "done")
    return state
