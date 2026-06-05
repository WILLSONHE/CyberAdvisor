"""AI 模拟交易日志（Wiki/数据/AI模拟交易日志.md）。"""
from __future__ import annotations

import os
from datetime import datetime

from ai_sim.config import JOURNAL_PATH, TOTAL_CASH
from ai_sim.portfolio_ops import active_positions, cash_available, equity_ratio, sync_prices
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


def append_tick_summary(tick_path: str, trades: list[dict], *, regime: str = "") -> None:
    _ensure_file()
    sync_prices()
    pos = active_positions()
    totals = _portfolio_totals(pos) if not pos.empty else {"total_cost": 0.0, "total_mkt": 0.0, "ratio": "—"}
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    tick = os.path.basename(tick_path).replace(".json", "")

    lines = [
        f"## {stamp} tick {tick[:2]}:{tick[2:]}",
        "",
        f"- **环境**：{regime or '—'}",
        f"- **现金**：{fmt_money(cash_available())} 元 | **市值**：{fmt_money(totals['total_mkt'])} 元 | **仓位**：{equity_ratio():.1%}",
        f"- **数据**：`{tick_path}`",
        "",
    ]
    if trades:
        lines.append("### 成交")
        lines.append("")
        for t in trades:
            if t.get("action") == "buy":
                lines.append(
                    f"- **买入** {t['name']}({t['code']}) {t['shares']} 股 @ {t['price']:.2f} "
                    f"≈ {fmt_money(t['amount'])} 元 | {t.get('style', '')} | {t.get('reason', '')}"
                )
            elif t.get("action") == "sell":
                lines.append(
                    f"- **卖出** {t['name']}({t['code']}) {t['shares']} 股 @ {t['price']:.2f} "
                    f"盈亏 {fmt_money(t.get('pnl', 0), signed=True)} ({t.get('pnl_pct', '')}) | {t.get('reason', '')}"
                )
        lines.append("")
    else:
        lines.append("*本 tick 无成交*\n")

    with open(JOURNAL_PATH, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
