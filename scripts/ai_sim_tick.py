"""AI 自主模拟盘单次 tick：采集 → 决策 → 成交 → 日志。"""
from __future__ import annotations

import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from ai_sim.collector import collect_tick
from ai_sim.journal import append_tick_summary
from ai_sim.portfolio_ops import ensure_xlsx
from ai_sim.schedule_util import is_scheduled_tick
from ai_sim.strategy import _sh_index, _target_equity_ratio, execute_decisions, plan_trades


def run(*, force: bool = False, tick_label: str = "") -> int:
    if not force and not is_scheduled_tick():
        print("非计划 tick 时刻，跳过（加 --force 强制执行）")
        return 0

    ensure_xlsx()
    path = collect_tick(force_label=tick_label)
    print(f"采集：{path}")

    sh = _sh_index(path)
    _, regime = _target_equity_ratio(sh)
    decisions = plan_trades(path)
    trades = execute_decisions(decisions)
    append_tick_summary(path, trades, regime=regime)

    if trades:
        print(f"成交 {len(trades)} 笔，详见 Wiki/数据/AI模拟交易日志.md")
    else:
        print("无成交")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="AI 模拟盘 15 分钟 tick")
    ap.add_argument("--force", action="store_true", help="忽略交易时段检查")
    ap.add_argument("--tick", default="", help="强制 tick 标签 HHMM")
    args = ap.parse_args()
    raise SystemExit(run(force=args.force, tick_label=args.tick))


if __name__ == "__main__":
    main()
