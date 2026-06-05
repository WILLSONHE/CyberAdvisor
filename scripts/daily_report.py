#!/usr/bin/env python3
"""
每日市场状态日报（daily.bat 第 5 步）

输出：Wiki/数据/市场状态日报.md
实现：scripts/market_daily/
规范：SKILL.md →「市场状态日报必抓字段」
"""
from __future__ import annotations

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

DATA_DIR = os.path.join(SCRIPT_DIR, "..", "Wiki", "数据")
OUTPUT = os.path.join(DATA_DIR, "市场状态日报.md")


def main() -> None:
    from market_daily.report import build_report

    print("[1/2] Fetching market data (indices / boards / tracking)...")
    report = build_report()
    print("[2/2] Writing report...")
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  Written to {OUTPUT}")
    print("Done.")


if __name__ == "__main__":
    main()
