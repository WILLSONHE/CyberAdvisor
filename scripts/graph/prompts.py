"""各角色 prompt 片段。"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from feishu.agent_prompts import _holdings_local_data, _read, _wiki_context, MARKET_DAILY  # noqa: E402


def _chan_summary_block(state: dict[str, Any]) -> str:
    idx = state.get("index_chan") or {}
    lines = ["### 指数缠论", json.dumps(idx, ensure_ascii=False, indent=2)[:2000]]
    for code, ch in (state.get("stock_chans") or {}).items():
        lines.append(f"**{code}**: {ch.get('buy_point')} | protect={ch.get('protect_price')}")
    return "\n".join(lines)


def analyst_prompt(role_key: str, role_label: str, state: dict[str, Any]) -> str:
    holder = state.get("holder") or "—"
    wiki = _wiki_context(max_chars=8000)
    market = _read(MARKET_DAILY, max_chars=4000)
    holdings = _holdings_local_data(holder) if holder and holder != "—" else ""
    return f"""## 角色
{role_label}（Graph 管线 · 只读分析）

## 任务
从 **{role_label}** 视角，对持有人 **{holder}** 的持仓与大盘给出 200–400 字 Markdown 分析。
须引用 Wiki/日更可核查出处；**不得**建议绕过缠论门禁。

## 缠论快照（本地已算，勿重算）
{_chan_summary_block(state)}

## Wiki 摘要
{wiki}

## 市场日报
{market}

## 持仓本机快照
{holdings}

输出：小标题 + 3–5 条 bullet，末尾一行「结论：…」。
"""


def debate_prompt(side: str, state: dict[str, Any], *, opponent: str = "") -> str:
    reports = state.get("analyst_reports") or {}
    merged = "\n\n".join(f"### {k}\n{v[:1200]}" for k, v in reports.items())
    return f"""你是 **{side}** 研究员。基于下方分析师摘要，撰写 {side} 论据（250–400 字）。
若引用缠论，须与本地快照一致；指数一卖时 Bull 不得主张激进开多。

## 分析师摘要
{merged[:6000]}

## 对手方上一轮（如有）
{opponent[:1500] or "（首轮）"}

输出 Markdown，标题 `## {side} 观点`。
"""


def research_manager_prompt(state: dict[str, Any]) -> str:
    return f"""你是 Research Manager。综合多空辩论与分析师报告，输出 **研究共识**（300–500 字）。
须明确：大盘方向、主线板块、对 {state.get('holder')} 持仓的整体态度（持有/减仓/观望）。
缠论门禁优先于 outlook 偏多。

## Bull
{(state.get('bull_case') or '')[:2000]}

## Bear
{(state.get('bear_case') or '')[:2000]}

## Quality Gate
{json.dumps(state.get('quality_gate') or {}, ensure_ascii=False)[:1500]}
"""


def trader_prompt(state: dict[str, Any]) -> str:
    return f"""你是 Trader。基于 Research Manager 结论，给出 **TraderProposal** Markdown：
- 每只持仓：动作（持有/减仓/做T/观望）、protect_price（来自缠论快照）、horizon（1/3/7日）
- 新开仓候选：仅当 hard_gate 未禁时列出

## RM 结论
{(state.get('research_manager') or '')[:2500]}

## 缠论 hard_gate 预览
{json.dumps(state.get('hard_gate') or {}, ensure_ascii=False)[:2000]}
"""


def risk_tier_prompt(tier: str, state: dict[str, Any]) -> str:
    labels = {"aggressive": "激进", "neutral": "中性", "conservative": "保守"}
    return f"""你是 **{labels.get(tier, tier)}** 风控官。审阅 Trader 提案，从 {labels.get(tier, tier)} 角度给出修正意见（150–250 字）。

## Trader 提案
{(state.get('trader_proposal') or '')[:3000]}
"""


def portfolio_manager_prompt(state: dict[str, Any]) -> str:
    risks = state.get("risk_tiers") or {}
    risk_block = "\n".join(f"### {k}\n{v[:800]}" for k, v in risks.items())
    return f"""你是 Portfolio Manager。综合 RM、Trader、三档风控，输出 **五档终局建议** Markdown 表格：
| 档位 | 仓位倾向 | 核心动作 | 缠论依据 |
|------|----------|----------|----------|

并附 3 条执行纪律。缠论 `allows_new_buy` 为硬约束。

## Research Manager
{(state.get('research_manager') or '')[:2000]}

## Trader
{(state.get('trader_proposal') or '')[:2000]}

## 风控
{risk_block[:2500]}
"""


def final_sug_prompt(holder: str, state: dict[str, Any], *, session: str | None = None) -> str:
    from feishu.agent_prompts import build_sug_prompt

    base = build_sug_prompt(holder, session=session)
    graph_ctx = f"""
## Graph 多 Agent 结论（须写入 §零 缠论 与 §四/§五，不得与之矛盾）

**analysis_id**: `{state.get('analysis_id')}`

### Portfolio Manager
{(state.get('portfolio_manager') or '')[:4000]}

### Hard Gate
{json.dumps(state.get('hard_gate') or {}, ensure_ascii=False, indent=2)[:2500]}

### 预算
spent=${state.get('budget', {}).get('spent_usd', 0):.2f} cap=${state.get('budget', {}).get('cap_usd', 5):.2f}
"""
    return base + "\n\n" + graph_ctx
