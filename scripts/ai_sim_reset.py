"""重置 AI 模拟盘：清空 xlsx（AI 持仓）、现金账本、交易日志。"""
from __future__ import annotations

import os
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from ai_sim.cash import _write_ledger
from ai_sim.config import JOURNAL_PATH, SIM_HOLDER, SIM_XLSX, TOTAL_CASH
from portfolio_utils import fmt_money
from ai_sim.runtime_params import reset_overrides
from sim_portfolio import _load_df, _save_df, init_sim_xlsx


def reset_ai_sim(*, keep_other_holders: bool = False) -> None:
    """
    从零重启 AI 模拟盘。
    - keep_other_holders=False：整表清空（默认）
    - keep_other_holders=True：仅删除持有人=AI 的行，保留其他持有人
    """
    if keep_other_holders and os.path.isfile(SIM_XLSX):
        df = _load_df()
        if not df.empty and "持有人" in df.columns:
            df = df[df["持有人"].astype(str).str.strip() != SIM_HOLDER].reset_index(drop=True)
        _save_df(df)
    else:
        if os.path.isfile(SIM_XLSX):
            os.remove(SIM_XLSX)
        init_sim_xlsx()

    _write_ledger(TOTAL_CASH)
    reset_overrides()

    os.makedirs(os.path.dirname(JOURNAL_PATH), exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = (
        "# AI 模拟交易日志\n\n"
        f"> 总资金 **{fmt_money(TOTAL_CASH)} 元**；持有人 **AI**；数据 `模拟持仓.xlsx`。\n"
        "> 规范见 `SKILL.md` → **AI 自主模拟盘**。\n\n"
        "---\n\n"
        f"## {stamp} 重置\n\n"
        f"- **操作**：模拟盘归零重启；现金 **{fmt_money(TOTAL_CASH)} 元**；持仓 **0**\n"
        f"- **说明**：此前测试数据（含错价 bug 导致的假亏损记录）已清除\n\n"
    )
    with open(JOURNAL_PATH, "w", encoding="utf-8") as f:
        f.write(header)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="重置 AI 模拟盘为 500 万空仓")
    ap.add_argument(
        "--keep-others",
        action="store_true",
        help="保留 xlsx 中非 AI 持有人的行（默认整表清空）",
    )
    args = ap.parse_args()
    reset_ai_sim(keep_other_holders=args.keep_others)
    print(f"已重置 AI 模拟盘：{SIM_XLSX}")
    print(f"现金：{fmt_money(TOTAL_CASH)} 元")
    print(f"日志：{JOURNAL_PATH}")


if __name__ == "__main__":
    main()
