"""AI 自主模拟盘单次 tick：采集 → Cloud Agent 调参 → 规则决策 → 成交 → 日志。"""
from __future__ import annotations

import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from ai_sim.agent_review import _load_env_file, review_tick
from ai_sim.collector import collect_tick
from ai_sim.journal import append_tick_summary
from ai_sim.portfolio_ops import ensure_xlsx
from ai_sim.schedule_util import (
    is_scheduled_tick,
    nearest_tick_label,
    tick_phase,
    tick_phase_label,
)
from ai_sim.strategy import execute_decisions, plan_trades


def run(*, force: bool = False, tick_label: str = "", agent: bool = True) -> int:
    if not force and not is_scheduled_tick():
        print("非计划 tick 时刻，跳过（加 --force 强制执行）")
        return 0

    ensure_xlsx()
    _load_env_file()
    label = tick_label or nearest_tick_label()
    phase = tick_phase(tick_label=label)
    print(f"阶段：{tick_phase_label(phase)} ({phase}) | tick={label}")
    path = collect_tick(force_label=label)
    print(f"采集：{path}")

    if agent:
        agent_result = review_tick(path, phase=phase)
        if agent_result.get("data_requests"):
            ext = agent_result["data_requests"]
            if ext.get("applied"):
                print(f"数据扩展启用：{[x['metric'] for x in ext['applied']]}")
            if ext.get("pending"):
                print(f"待扩展指标：{[x['metric'] for x in ext['pending']]}")
        if agent_result.get("skipped"):
            print(f"Agent 跳过：{agent_result.get('reason')}")
        elif agent_result.get("ok"):
            applied = agent_result.get("applied") or {}
            if applied:
                print(f"Agent 调参：{applied}")
            else:
                print("Agent 分析完成，未调参（详见交易日志）")
        else:
            print(f"Agent 失败：{agent_result.get('error', 'unknown')}（详见交易日志）")
    else:
        agent_result = None

    trade_plan = plan_trades(path, agent=agent_result)
    trades = execute_decisions(trade_plan.decisions, tick_quotes=trade_plan.quotes)
    new_journal = append_tick_summary(
        path,
        trades,
        regime=trade_plan.regime,
        plan=trade_plan,
        agent=agent_result if agent else None,
        phase=phase,
    )

    try:
        from feishu.env import FeishuConfig
        from feishu.notify import push_ai_sim_journal

        push_ai_sim_journal(FeishuConfig.load(), new_block=new_journal)
    except Exception as e:
        print(f"飞书推送跳过：{e}")

    if trades:
        print(f"成交 {len(trades)} 笔，详见 Wiki/数据/AI模拟交易日志.md")
    else:
        print("无成交，详见 Wiki/数据/AI模拟交易日志.md")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="AI 模拟盘 15 分钟 tick")
    ap.add_argument("--force", action="store_true", help="忽略交易时段检查")
    ap.add_argument("--tick", default="", help="强制 tick 标签 HHMM")
    ap.add_argument("--no-agent", action="store_true", help="跳过 Cloud Agent 分析/调参")
    args = ap.parse_args()
    raise SystemExit(run(force=args.force, tick_label=args.tick, agent=not args.no_agent))


if __name__ == "__main__":
    main()
