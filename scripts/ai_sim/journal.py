"""AI 模拟交易日志（Wiki/数据/AI模拟交易日志.md）。"""
from __future__ import annotations

import os
from datetime import datetime

from ai_sim.agent_review import _format_agent_block
from ai_sim.data_requests import format_data_extension_block
from ai_sim.schedule_util import tick_phase, tick_phase_label
from ai_sim.config import JOURNAL_PATH, TOTAL_CASH
from ai_sim.portfolio_ops import active_positions, cash_available, equity_ratio, sync_prices, total_assets
from ai_sim.strategy import TradePlan
from portfolio_utils import fmt_money
from sim_portfolio import _portfolio_totals


def _ensure_file() -> None:
    if os.path.isfile(JOURNAL_PATH):
        return
    os.makedirs(os.path.dirname(JOURNAL_PATH), exist_ok=True)
    header = (
        "# AI 模拟交易日志\n\n"
        f"> 总资金 **{fmt_money(TOTAL_CASH)} 元**；持有人 **AI**；数据 `模拟持仓.xlsx`。\n"
        "> 规范见 `SKILL.md` → **AI 自主模拟盘**。\n\n"
        "---\n\n"
    )
    with open(JOURNAL_PATH, "w", encoding="utf-8") as f:
        f.write(header)


def _format_trade(t: dict) -> list[str]:
    action = "买入" if t.get("action") == "buy" else "卖出"
    head = f"- **{action}** {t['name']}({t['code']}) {t['shares']} 股 @ {t['price']:.2f}"
    if t.get("action") == "buy":
        head += f" ≈ {fmt_money(t['amount'])} 元"
    else:
        head += f" 盈亏 {fmt_money(t.get('pnl', 0), signed=True)} ({t.get('pnl_pct', '')})"
    lines = [head]
    if t.get("reason_kind"):
        lines.append(f"  - **类型**：{t['reason_kind']}")
    if t.get("style"):
        lines.append(f"  - **风格**：{t['style']}")
    if t.get("reason"):
        lines.append(f"  - **原因**：{t['reason']}")
    if t.get("price_src"):
        lines.append(f"  - **定价**：{t['price_src']}")
    return lines


def _format_planned(d) -> list[str]:
    action = "买入" if d.action == "buy" else "卖出"
    lines = [f"- **计划{action}** {d.name}({d.code})"]
    lines.append(f"  - **类型**：{d.reason_kind}")
    if d.style:
        lines.append(f"  - **风格**：{d.style}")
    if d.reason:
        lines.append(f"  - **原因**：{d.reason}")
    if d.action == "buy" and d.amount > 0:
        lines.append(f"  - **预算**：约 {fmt_money(d.amount)} 元")
    return lines


def append_tick_summary(
    tick_path: str,
    trades: list[dict],
    *,
    regime: str = "",
    plan: TradePlan | None = None,
    agent: dict | None = None,
    phase: str = "",
) -> str:
    _ensure_file()
    sync_prices()
    pos = active_positions()
    totals = _portfolio_totals(pos) if not pos.empty else {"total_cost": 0.0, "total_mkt": 0.0, "ratio": "—"}
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    tick = os.path.basename(tick_path).replace(".json", "")
    phase = phase or tick_phase(tick_label=tick)
    phase_cn = tick_phase_label(phase)
    target_ratio = plan.target_ratio if plan else None
    current_ratio = plan.current_ratio if plan else equity_ratio()
    lines = [
        f"## {stamp} tick {tick[:2]}:{tick[2:]} · {phase_cn}",
        "",
        f"- **阶段**：{phase} | **环境**：{regime or (plan.regime if plan else '—')}",
    ]
    if target_ratio is not None:
        lines.append(
            f"- **仓位目标**：{target_ratio:.0%} | **当前**：{current_ratio:.1%} | "
            f"**现金**：{fmt_money(cash_available())} 元 | **市值**：{fmt_money(totals['total_mkt'])} 元 | "
            f"**总资产**：{fmt_money(total_assets())} 元"
        )
    else:
        lines.append(
            f"- **现金**：{fmt_money(cash_available())} 元 | **市值**：{fmt_money(totals['total_mkt'])} 元 | "
            f"**总资产**：{fmt_money(total_assets())} 元 | **仓位**：{equity_ratio():.1%}"
        )
    lines.append(f"- **数据**：`{tick_path}`")
    if plan and plan.tick_note:
        lines.append(f"- **说明**：{plan.tick_note}")
    lines.append("")

    agent_lines = _format_agent_block(agent)
    if agent_lines:
        lines.extend(agent_lines)

    data_ext_lines = format_data_extension_block((agent or {}).get("data_requests"))
    if data_ext_lines:
        lines.extend(data_ext_lines)

    if trades:
        lines.append("### 成交")
        lines.append("")
        for t in trades:
            lines.extend(_format_trade(t))
        if plan and plan.buy_skip:
            lines.append(f"- **未买入**：{plan.buy_skip}")
        lines.append("")
    else:
        lines.append("*本 tick 无成交*")
        lines.append("")
        if plan and plan.buy_skip:
            lines.append(f"- **未买入**：{plan.buy_skip}")
            lines.append("")
        if plan and plan.decisions and not trades:
            failed = [d for d in plan.decisions]
            if failed:
                lines.append("### 计划未执行")
                lines.append("")
                for d in failed:
                    lines.extend(_format_planned(d))
                lines.append("")

    with open(JOURNAL_PATH, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return "\n".join(lines) + "\n"
